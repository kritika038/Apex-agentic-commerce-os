'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  CameraIcon,
  RefreshCwIcon,
  SparklesIcon,
  ShieldCheckIcon,
  AlertTriangleIcon
} from '@/components/ui/Icons';
import { Button } from '@/components/ui/Button';

export type CameraState = 'idle' | 'requesting' | 'ready' | 'error';

interface LiveVirtualTryOnProps {
  product: {
    id: string;
    name: string;
    brand?: string;
    category?: string;
    garment_type?: string;
    price: number;
    image_url?: string;
    color?: string;
    size?: string;
  };
  onCapture: (capturedFile: File) => void;
  onSwitchToUpload: () => void;
  onClose?: () => void;
}

export function LiveVirtualTryOn({
  product,
  onCapture,
  onSwitchToUpload
}: LiveVirtualTryOnProps) {
  const [cameraState, setCameraState] = useState<CameraState>('idle');
  const [facingMode, setFacingMode] = useState<'user' | 'environment'>('user');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isCapturing, setIsCapturing] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const checkIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef<boolean>(true);

  // Stop all camera tracks systematically
  const stopCameraStream = useCallback(() => {
    if (checkIntervalRef.current) {
      clearInterval(checkIntervalRef.current);
      checkIntervalRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch {
          // ignore
        }
      });
      streamRef.current = null;
    }

    if (videoRef.current) {
      try {
        videoRef.current.pause();
        videoRef.current.srcObject = null;
      } catch {
        // ignore
      }
    }
  }, []);

  // Request & start camera stream
  const startCamera = useCallback(async (mode: 'user' | 'environment') => {
    stopCameraStream();
    setErrorMessage(null);
    setCameraState('requesting');

    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      if (isMountedRef.current) {
        setCameraState('error');
        setErrorMessage("Camera access isn't available in this browser. You can upload a photo instead.");
      }
      return;
    }

    try {
      console.log('[VTO CAMERA] Requesting getUserMedia for mode:', mode);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: mode,
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false // Strictly no microphone
      });

      if (!isMountedRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }

      streamRef.current = stream;
      const video = videoRef.current;

      if (!video) {
        console.warn('[VTO CAMERA] videoRef.current is not yet mounted');
        return;
      }

      // Explicit WebKit/Safari initialization
      video.muted = true;
      video.playsInline = true;
      video.autoplay = true;
      video.srcObject = stream;

      // Attach diagnostic event listeners
      const logEvent = (name: string) => {
        console.log(`[VTO CAMERA] event:${name}`, {
          readyState: video.readyState,
          paused: video.paused,
          videoWidth: video.videoWidth,
          videoHeight: video.videoHeight,
          currentTime: video.currentTime
        });
      };

      video.onloadedmetadata = () => logEvent('loadedmetadata');
      video.onloadeddata = () => logEvent('loadeddata');
      video.oncanplay = () => logEvent('canplay');
      video.onplaying = () => logEvent('playing');
      video.onwaiting = () => logEvent('waiting');
      video.onstalled = () => logEvent('stalled');
      video.onsuspend = () => logEvent('suspend');
      video.onerror = (e) => console.error('[VTO CAMERA] video error event:', e);

      try {
        await video.play();
      } catch (playErr) {
        console.warn('[VTO CAMERA] Initial video.play() warning:', playErr);
      }

      // Verification loop for decoded video frames (videoWidth > 0 && readyState >= 2)
      let elapsedMs = 0;
      const pollIntervalMs = 100;
      const maxWaitMs = 5000;

      if (checkIntervalRef.current) {
        clearInterval(checkIntervalRef.current);
      }

      checkIntervalRef.current = setInterval(async () => {
        elapsedMs += pollIntervalMs;
        const currentVideo = videoRef.current;

        if (!currentVideo || !isMountedRef.current) {
          if (checkIntervalRef.current) clearInterval(checkIntervalRef.current);
          return;
        }

        const isReady =
          currentVideo.videoWidth > 0 &&
          currentVideo.videoHeight > 0 &&
          currentVideo.readyState >= 2 &&
          !currentVideo.paused;

        console.log('[VTO CAMERA] verification check:', {
          elapsedMs,
          readyState: currentVideo.readyState,
          videoWidth: currentVideo.videoWidth,
          videoHeight: currentVideo.videoHeight,
          paused: currentVideo.paused,
          isReady
        });

        if (isReady) {
          if (checkIntervalRef.current) {
            clearInterval(checkIntervalRef.current);
            checkIntervalRef.current = null;
          }
          if (isMountedRef.current) {
            setCameraState('ready');
          }
          return;
        }

        // Retry play if stalled in Safari
        if (currentVideo.paused && elapsedMs % 500 === 0) {
          try {
            await currentVideo.play();
          } catch {
            // ignore
          }
        }

        if (elapsedMs >= maxWaitMs) {
          if (checkIntervalRef.current) {
            clearInterval(checkIntervalRef.current);
            checkIntervalRef.current = null;
          }
          if (currentVideo.videoWidth > 0 && currentVideo.videoHeight > 0) {
            if (isMountedRef.current) setCameraState('ready');
          } else {
            console.warn('[VTO CAMERA] Timed out waiting for decoded frames');
            if (isMountedRef.current) {
              setCameraState('error');
              setErrorMessage('Camera preview could not start. You can upload a photo instead.');
            }
          }
        }
      }, pollIntervalMs);
    } catch (err: unknown) {
      console.warn('[VTO CAMERA] Camera Access Error:', err);
      if (!isMountedRef.current) return;

      const errName = (err as { name?: string })?.name;
      setCameraState('error');
      if (errName === 'NotAllowedError' || errName === 'PermissionDeniedError') {
        setErrorMessage('Camera access was denied. You can upload a photo instead.');
      } else if (errName === 'NotFoundError' || errName === 'DevicesNotFoundError') {
        setErrorMessage('No camera was detected on this device. You can upload a photo instead.');
      } else {
        setErrorMessage("Camera access wasn't available. You can upload a photo instead.");
      }
    }
  }, [stopCameraStream]);

  // Lifecycle management
  useEffect(() => {
    isMountedRef.current = true;
    startCamera(facingMode);

    return () => {
      isMountedRef.current = false;
      stopCameraStream();
    };
  }, [facingMode, startCamera, stopCameraStream]);

  // Capture frame from active video element with pixel verification
  const handleCapture = () => {
    const video = videoRef.current;
    if (!video || cameraState !== 'ready' || video.videoWidth === 0 || video.videoHeight === 0) {
      setErrorMessage('Camera frame is not ready. Please wait a moment and try again.');
      return;
    }

    setIsCapturing(true);

    try {
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });

      if (!ctx) {
        setIsCapturing(false);
        setErrorMessage('Failed to capture camera frame. Please try again.');
        return;
      }

      if (facingMode === 'user') {
        // Mirror for front-facing selfie capture
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
      }
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Verify canvas contains actual camera pixels and is not completely black
      const sampleWidth = Math.min(canvas.width, 100);
      const sampleHeight = Math.min(canvas.height, 100);
      const sampleData = ctx.getImageData(0, 0, sampleWidth, sampleHeight).data;

      let totalBrightness = 0;
      for (let i = 0; i < sampleData.length; i += 4) {
        totalBrightness += (sampleData[i] + sampleData[i + 1] + sampleData[i + 2]) / 3;
      }
      const avgBrightness = totalBrightness / (sampleData.length / 4);

      console.log('[VTO CAMERA] capture pixel check:', {
        width: canvas.width,
        height: canvas.height,
        avgBrightness
      });

      if (avgBrightness < 1.0) {
        setIsCapturing(false);
        setErrorMessage('Camera frame is not ready. Please wait a moment and try again.');
        return;
      }

      canvas.toBlob(
        (blob) => {
          if (blob && blob.size > 0) {
            const capturedFile = new File([blob], `live_camera_${Date.now()}.jpg`, {
              type: 'image/jpeg'
            });
            stopCameraStream();
            onCapture(capturedFile);
          } else {
            setErrorMessage('Frame capture failed. Please try again.');
          }
          setIsCapturing(false);
        },
        'image/jpeg',
        0.95
      );
    } catch (err) {
      console.error('[VTO CAMERA] Capture error:', err);
      setIsCapturing(false);
      setErrorMessage('Frame capture error. You can upload a photo instead.');
    }
  };

  const isReady = cameraState === 'ready';
  const isRequesting = cameraState === 'requesting' || cameraState === 'idle';
  const isError = cameraState === 'error';

  return (
    <div className="space-y-4">
      {/* Viewport Box - Always real dimensions */}
      <div className="relative rounded-2xl overflow-hidden bg-slate-950 aspect-[4/5] sm:aspect-[4/3] max-h-[55vh] flex items-center justify-center border border-slate-800 shadow-2xl">
        
        {/* Video element is ALWAYS mounted and visible in layout */}
        <video
          ref={videoRef}
          playsInline
          muted
          autoPlay
          className={`w-full h-full object-cover transition-transform duration-300 ${
            facingMode === 'user' ? 'scale-x-[-1]' : ''
          }`}
        />

        {/* Live Camera Overlays when Ready */}
        {isReady && (
          <>
            {/* Live Indicator Badge */}
            <div className="absolute top-3 left-3 bg-slate-900/85 backdrop-blur-md px-2.5 py-1 rounded-full text-[11px] font-semibold text-emerald-400 border border-slate-700/50 flex items-center gap-1.5 shadow-xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Live Camera Preview</span>
            </div>

            {/* Product Variant Tag */}
            <div className="absolute top-3 right-3 bg-slate-900/85 backdrop-blur-md px-2.5 py-1 rounded-full text-[11px] font-medium text-slate-200 border border-slate-700/50 flex items-center gap-1.5 shadow-xs">
              <span className="truncate max-w-[120px]">{product.brand || 'Apex'}</span>
              {product.color && <span>• {product.color}</span>}
            </div>

            {/* Upper-Body Framing Guide Box */}
            <div className="absolute inset-x-8 top-10 bottom-16 border-2 border-dashed border-white/40 rounded-3xl pointer-events-none flex flex-col items-center justify-between p-4">
              <span className="text-[10px] uppercase font-bold tracking-widest text-white/70 bg-slate-900/60 px-2 py-0.5 rounded">
                Align Face &amp; Shoulders
              </span>
              <span className="text-[10px] uppercase font-bold tracking-widest text-white/70 bg-slate-900/60 px-2 py-0.5 rounded">
                Torso
              </span>
            </div>

            {/* Interactive Alignment Guide Message */}
            <div className="absolute inset-x-0 bottom-3 flex justify-center pointer-events-none">
              <div className="bg-slate-900/85 backdrop-blur-md text-white text-[11px] px-3.5 py-1.5 rounded-full border border-slate-700/50 flex items-center gap-2 shadow-md">
                <SparklesIcon className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                <span>Align your shoulders and torso inside the frame</span>
              </div>
            </div>
          </>
        )}

        {/* Connecting / Requesting Overlay on top of actively decoding video */}
        {isRequesting && (
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-xs flex flex-col items-center justify-center text-slate-400 space-y-3 z-10">
            <div className="w-10 h-10 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs font-medium text-slate-300">Connecting to camera...</p>
            <p className="text-[11px] text-slate-500">Your live camera preview stays on this device.</p>
          </div>
        )}

        {/* Error / Denied Screen */}
        {isError && (
          <div className="absolute inset-0 bg-slate-950 flex flex-col items-center justify-center p-6 text-center text-slate-300 space-y-4 max-w-sm z-20">
            <div className="w-12 h-12 rounded-full bg-slate-800 text-amber-400 mx-auto flex items-center justify-center border border-slate-700">
              <AlertTriangleIcon className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-white">Camera Access Required</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                {errorMessage || "Camera access wasn't available. You can upload a photo instead."}
              </p>
            </div>
            <div className="pt-2 w-full">
              <Button
                onClick={onSwitchToUpload}
                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold py-2.5 cursor-pointer"
              >
                Continue with Photo Upload
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Action Controls */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            disabled={!isReady}
            onClick={() => setFacingMode((prev) => (prev === 'user' ? 'environment' : 'user'))}
            className="text-xs py-2.5 px-3 flex items-center gap-1.5 text-slate-700 hover:bg-slate-50 cursor-pointer disabled:opacity-50"
          >
            <RefreshCwIcon className="w-3.5 h-3.5" />
            <span>Flip</span>
          </Button>

          <Button
            onClick={handleCapture}
            disabled={!isReady || isCapturing}
            className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold py-2.5 shadow-md flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
          >
            <CameraIcon className="w-4 h-4" />
            <span>{isCapturing ? 'Capturing...' : 'Capture & Try On'}</span>
          </Button>

          <Button
            variant="outline"
            onClick={onSwitchToUpload}
            className="text-xs py-2.5 px-3 text-slate-700 hover:bg-slate-50 cursor-pointer"
          >
            Upload Photo
          </Button>
        </div>

        {/* Privacy Transparency */}
        <div className="p-2.5 bg-slate-50/80 rounded-lg border border-slate-200/80 flex items-center gap-2 text-[11px] text-slate-500">
          <ShieldCheckIcon className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>Camera preview runs on your device. Captured snapshot is securely processed for AI garment synthesis.</span>
        </div>
      </div>
    </div>
  );
}
