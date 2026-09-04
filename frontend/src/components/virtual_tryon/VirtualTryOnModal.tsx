'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  XIcon,
  SparklesIcon,
  ShieldCheckIcon,
  UploadIcon,
  RefreshCwIcon,
  ShoppingBagIcon,
  AlertTriangleIcon,
  CameraIcon
} from '@/components/ui/Icons';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { apiClient, extractErrorMessage, API_BASE_URL } from '@/lib/api';
import { TryOnJobStatusResponse } from '@/lib/types/virtual_tryon';
import { LiveVirtualTryOn } from './LiveVirtualTryOn';
import { ProductImage } from '@/components/ui/ProductImage';

interface VirtualTryOnModalProps {
  isOpen: boolean;
  onClose: () => void;
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
  } | null;
  sessionId?: string;
  onAddToCart?: (productId: string) => void;
  onBuyNow?: (productId: string) => void;
  onComparePrices?: (productId: string) => void;
  onSelectProductToTry?: (productId: string) => void;
}

type ModalState = 'camera' | 'intro' | 'upload' | 'processing' | 'result' | 'error';
type VtoTabMode = 'camera' | 'photo';

export function VirtualTryOnModal({
  isOpen,
  onClose,
  product,
  sessionId,
  onAddToCart,
  onSelectProductToTry
}: VirtualTryOnModalProps) {
  const [tabMode, setTabMode] = useState<VtoTabMode>('camera');
  const [modalState, setModalState] = useState<ModalState>('camera');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [consentGiven, setConsentGiven] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [jobData, setJobData] = useState<TryOnJobStatusResponse | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset state when opening/switching product
  useEffect(() => {
    if (isOpen) {
      setTabMode('camera');
      setModalState('camera');
      setSelectedFile(null);
      setPreviewUrl(null);
      setConsentGiven(false);
      setErrorMessage(null);
      setJobData(null);
    } else {
      setErrorMessage(null);
    }
  }, [isOpen, product?.id]);

  if (!isOpen || !product) return null;

  const handleTabSwitch = (mode: VtoTabMode) => {
    setTabMode(mode);
    setErrorMessage(null);
    if (mode === 'camera') {
      setModalState('camera');
    } else {
      if (selectedFile) {
        setModalState('upload');
      } else {
        setModalState('intro');
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage('File exceeds 10MB limit. Please upload a smaller photo.');
      return;
    }

    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setErrorMessage('Please upload a valid JPEG, PNG, or WEBP photo.');
      return;
    }

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setErrorMessage(null);
    setTabMode('photo');
    setModalState('upload');
  };

  const processTryOnJob = async (fileToProcess: File) => {
    setModalState('processing');
    setLoading(true);
    setErrorMessage(null);

    const formData = new FormData();
    formData.append('product_id', product.id);
    formData.append('consent', 'true');
    if (sessionId) formData.append('session_id', sessionId);
    if (product.color) formData.append('variant_id', `${product.color}-${product.size || ''}`);
    formData.append('background', 'true');
    formData.append('photo', fileToProcess);

    try {
      const res = await apiClient.post<TryOnJobStatusResponse>('/virtual-tryon/jobs', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      const jobId = res.data.job_id;
      setJobData(res.data);

      // Poll job status with real progress streaming
      let attempts = 0;
      const pollInterval = setInterval(async () => {
        attempts++;
        try {
          const statusRes = await apiClient.get<TryOnJobStatusResponse>(
            `/virtual-tryon/jobs/${jobId}${sessionId ? `?session_id=${sessionId}` : ''}`
          );
          setJobData(statusRes.data);

          if (statusRes.data.status === 'COMPLETED') {
            clearInterval(pollInterval);
            setModalState('result');
            setLoading(false);
          } else if (statusRes.data.status === 'FAILED' || statusRes.data.status === 'CANCELLED') {
            clearInterval(pollInterval);
            setErrorMessage(statusRes.data.error_message || 'Virtual try-on synthesis failed.');
            setModalState('error');
            setLoading(false);
          } else if (attempts > 300) { // 10 minutes timeout
            clearInterval(pollInterval);
            setErrorMessage('Try-on synthesis took longer than expected. Please try again.');
            setModalState('error');
            setLoading(false);
          }
        } catch (err: unknown) {
          clearInterval(pollInterval);
          setErrorMessage(extractErrorMessage(err, 'Failed to retrieve try-on preview.'));
          setModalState('error');
          setLoading(false);
        }
      }, 1000);

    } catch (err: unknown) {
      setErrorMessage(extractErrorMessage(err, 'Failed to start virtual try-on.'));
      setModalState('error');
      setLoading(false);
    }
  };

  const handleCapturedFromCamera = (capturedFile: File) => {
    setSelectedFile(capturedFile);
    setPreviewUrl(URL.createObjectURL(capturedFile));
    setConsentGiven(true);
    processTryOnJob(capturedFile);
  };

  const handleGenerateTryOn = async () => {
    if (!selectedFile || !consentGiven) return;
    processTryOnJob(selectedFile);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm animate-in fade-in duration-200 font-sans">
      <div className="bg-white rounded-2xl shadow-2xl max-w-xl w-full max-h-[92vh] flex flex-col overflow-hidden border border-slate-200">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-3.5 border-b border-slate-100 bg-slate-50/70">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-xs">
              <SparklesIcon className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide">AI Virtual Try-On</h3>
                <Badge variant="purple" className="text-[10px] px-1.5 py-0.5">FASHN v1.5</Badge>
              </div>
              <p className="text-[11px] text-slate-500">See how this looks on you</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <XIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Selector Tabs (only when in setup / setup states) */}
        {['camera', 'intro', 'upload'].includes(modalState) && (
          <div className="flex border-b border-slate-200 bg-slate-100/50 p-1 gap-1">
            <button
              type="button"
              onClick={() => handleTabSwitch('camera')}
              className={`flex-1 py-2 text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                tabMode === 'camera'
                  ? 'bg-white text-indigo-600 shadow-xs border border-slate-200/60'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <CameraIcon className="w-3.5 h-3.5" />
              <span>Live Camera</span>
            </button>
            <button
              type="button"
              onClick={() => handleTabSwitch('photo')}
              className={`flex-1 py-2 text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                tabMode === 'photo'
                  ? 'bg-white text-indigo-600 shadow-xs border border-slate-200/60'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <UploadIcon className="w-3.5 h-3.5" />
              <span>Upload Photo</span>
            </button>
          </div>
        )}

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-5">

          {/* MODE: LIVE CAMERA */}
          {modalState === 'camera' && (
            <LiveVirtualTryOn
              product={product}
              onCapture={handleCapturedFromCamera}
              onSwitchToUpload={() => handleTabSwitch('photo')}
              onClose={onClose}
            />
          )}

          {/* MODE: PHOTO INTRO */}
          {modalState === 'intro' && (
            <div className="space-y-5">
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 flex items-center gap-3.5">
                <div className="w-14 h-14 rounded-lg bg-white border border-slate-200 overflow-hidden relative shrink-0">
                  <ProductImage
                    src={product.image_url}
                    alt={product.name}
                    productName={product.name}
                    category={product.category}
                    className="w-full h-full object-cover"
                    containerClassName="w-full h-full"
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] text-indigo-600 font-bold uppercase tracking-wider">{product.brand || 'Apex'}</p>
                  <h4 className="text-xs font-bold text-slate-900 truncate">{product.name}</h4>
                  <p className="text-xs text-slate-500">Selected: <span className="font-semibold text-slate-800">{product.color || 'Standard'}</span> • ₹{product.price.toLocaleString('en-IN')}</p>
                </div>
              </div>

              <div className="space-y-2.5">
                <h4 className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">Photo Guidelines</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <div className="p-3 bg-indigo-50/50 rounded-lg border border-indigo-100 text-xs text-indigo-950 space-y-1">
                    <p className="font-semibold flex items-center gap-1.5">
                      <CameraIcon className="w-3.5 h-3.5 text-indigo-600" /> Full Person View
                    </p>
                    <p className="text-indigo-800/80 text-[11px]">Clear photo with good lighting and visible pose.</p>
                  </div>
                  <div className="p-3 bg-emerald-50/50 rounded-lg border border-emerald-100 text-xs text-emerald-950 space-y-1">
                    <p className="font-semibold flex items-center gap-1.5">
                      <ShieldCheckIcon className="w-3.5 h-3.5 text-emerald-600" /> Privacy Protected
                    </p>
                    <p className="text-emerald-800/80 text-[11px]">Short-lived vault storage with strict tenant isolation.</p>
                  </div>
                </div>
              </div>

              <div className="pt-2">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileSelect}
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                />
                <Button
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full bg-indigo-600 hover:bg-indigo-700 text-white shadow-md flex items-center justify-center gap-2 py-2.5 text-xs font-bold"
                >
                  <UploadIcon className="w-4 h-4" /> Upload Photo from Device
                </Button>
              </div>
            </div>
          )}

          {/* MODE: PHOTO UPLOAD & CONSENT */}
          {modalState === 'upload' && previewUrl && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                {/* Person Photo */}
                <div className="space-y-1">
                  <p className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Your Photo</p>
                  <div className="aspect-[3/4] rounded-xl overflow-hidden border border-slate-200 bg-slate-100 relative shadow-inner">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={previewUrl} alt="Upload preview" className="w-full h-full object-cover" />
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="absolute bottom-2 right-2 bg-slate-900/80 hover:bg-slate-900 text-white text-[10px] px-2 py-1 rounded-md backdrop-blur-xs transition-colors cursor-pointer"
                    >
                      Change
                    </button>
                  </div>
                </div>

                {/* Selected Product */}
                <div className="space-y-1">
                  <p className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Selected Item</p>
                  <div className="aspect-[3/4] rounded-xl overflow-hidden border border-slate-200 bg-white p-3 flex flex-col items-center justify-between">
                    <div className="w-full flex-1 relative flex items-center justify-center">
                      <ProductImage
                        src={product.image_url}
                        alt={product.name}
                        productName={product.name}
                        category={product.category}
                        className="max-h-full object-contain"
                        containerClassName="w-full h-full bg-transparent"
                      />
                    </div>
                    <div className="w-full text-center pt-2 border-t border-slate-100">
                      <p className="text-xs font-bold text-slate-900 truncate">{product.name}</p>
                      <p className="text-[11px] text-slate-500 font-medium">Color: {product.color || 'Standard'}</p>
                      <p className="text-xs text-indigo-600 font-semibold">₹{product.price.toLocaleString('en-IN')}</p>
                    </div>
                  </div>
                </div>
              </div>

              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
              />

              {/* Consent Box */}
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                <label className="flex items-start gap-2.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={consentGiven}
                    onChange={(e) => setConsentGiven(e.target.checked)}
                    className="mt-0.5 w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <div className="text-xs text-slate-700 leading-relaxed">
                    <span className="font-semibold text-slate-900">Generate a virtual try-on preview using my photo.</span>
                    <p className="text-slate-500 text-[11px] mt-0.5">
                      Your photo is used solely for visual preview synthesis and is protected under strict access isolation.
                    </p>
                  </div>
                </label>
              </div>

              {errorMessage && (
                <div className="p-3 bg-rose-50 text-rose-700 border border-rose-200 rounded-lg text-xs flex items-center gap-2">
                  <AlertTriangleIcon className="w-4 h-4 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              <div className="flex gap-2.5 pt-1">
                <Button
                  variant="outline"
                  onClick={() => setModalState('intro')}
                  className="flex-1 py-2 text-xs"
                >
                  Back
                </Button>
                <Button
                  onClick={handleGenerateTryOn}
                  disabled={!consentGiven || loading}
                  className="flex-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 text-xs shadow-md disabled:opacity-50"
                >
                  <SparklesIcon className="w-3.5 h-3.5 mr-1.5" /> Generate Try-On
                </Button>
              </div>
            </div>
          )}

          {/* STATE: PROCESSING */}
          {modalState === 'processing' && (
            <div className="py-8 px-4 flex flex-col items-center justify-center space-y-6 max-w-md mx-auto">
              {/* Header Badge */}
              <div className="flex items-center gap-2 px-3 py-1 bg-indigo-50 border border-indigo-200/80 rounded-full text-xs font-bold text-indigo-700 shadow-2xs">
                <SparklesIcon className="w-3.5 h-3.5 text-indigo-600 animate-pulse" />
                <span>AI VIRTUAL TRY-ON • FASHN v1.5</span>
              </div>

              {/* Progress Title & Percentage */}
              <div className="text-center space-y-1 w-full">
                <div className="flex items-center justify-between text-xs font-bold text-slate-700 px-0.5">
                  <span className="truncate">{jobData?.progress_message || 'Generating AI try-on...'}</span>
                  <span className="font-mono text-indigo-600 text-sm ml-2">
                    {Math.min(100, Math.max(5, jobData?.progress_percent || 5))}%
                  </span>
                </div>

                {/* Animated Progress Bar */}
                <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200 shadow-inner">
                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 via-indigo-600 to-indigo-700 rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${Math.min(100, Math.max(5, jobData?.progress_percent || 5))}%` }}
                  />
                </div>

                {/* Step Subtitle */}
                {jobData?.sampling_step && jobData?.sampling_total ? (
                  <p className="text-[11px] font-mono text-slate-500 text-right mt-1">
                    Sampling step {jobData.sampling_step} / {jobData.sampling_total}
                  </p>
                ) : (
                  <p className="text-[11px] text-slate-400 text-left mt-1">
                    Applying {product.color || 'selected'} variant on Apple Silicon MPS
                  </p>
                )}
              </div>

              {/* Stage Checklist */}
              {(() => {
                const STAGES = [
                  { key: 'PREPARING', label: 'Preparing your photo' },
                  { key: 'GARMENT_VALIDATION', label: 'Validating selected garment' },
                  { key: 'POSE_DETECTION', label: 'Detecting pose & body anchors' },
                  { key: 'GARMENT_PREPARATION', label: 'Preparing garment features' },
                  { key: 'DIFFUSION', label: 'Generating AI try-on (diffusion sampling)' },
                  { key: 'FINALIZING', label: 'Finalizing visual preview' },
                ];

                const currentStage = jobData?.processing_stage || 'PREPARING';
                const stageIndexMap: Record<string, number> = {
                  'PREPARING': 0,
                  'GARMENT_VALIDATION': 1,
                  'POSE_DETECTION': 2,
                  'GARMENT_PREPARATION': 3,
                  'DIFFUSION': 4,
                  'FINALIZING': 5,
                  'COMPLETED': 6,
                };
                const currentIdx = stageIndexMap[currentStage] ?? 0;

                return (
                  <div className="w-full p-3.5 bg-slate-50/80 rounded-xl border border-slate-200/90 space-y-2 text-xs">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                      Inference Pipeline
                    </p>
                    {STAGES.map((stg, sIdx) => {
                      const isCompleted = currentIdx > sIdx;
                      const isCurrent = currentIdx === sIdx;

                      return (
                        <div
                          key={stg.key}
                          className={`flex items-center gap-2.5 transition-all ${
                            isCompleted
                              ? 'text-emerald-700 font-semibold'
                              : isCurrent
                              ? 'text-indigo-700 font-bold'
                              : 'text-slate-400 font-normal'
                          }`}
                        >
                          {isCompleted ? (
                            <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-[10px] font-bold shrink-0">
                              ✓
                            </span>
                          ) : isCurrent ? (
                            <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-[10px] font-bold shrink-0 animate-pulse">
                              ●
                            </span>
                          ) : (
                            <span className="w-4 h-4 rounded-full bg-slate-200/70 text-slate-400 flex items-center justify-center text-[10px] shrink-0">
                              ○
                            </span>
                          )}
                          <span className="truncate">{stg.label}</span>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}

              <p className="text-[11px] text-slate-400 text-center leading-relaxed">
                Local FASHN VTON v1.5 neural inference running safely on private local GPU.
              </p>
            </div>
          )}

          {/* STATE: RESULT */}
          {modalState === 'result' && jobData && (
            <div className="space-y-4">
              <div className="relative rounded-2xl overflow-hidden border border-slate-200 bg-slate-900 shadow-lg aspect-[4/5] flex items-center justify-center">
                {jobData.preview_image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={`${API_BASE_URL.replace(/\/api\/v1\/?$/, '')}${jobData.preview_image_url}`}
                    alt="AI Virtual Try-On Result"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="text-center p-6 text-slate-400">
                    <AlertTriangleIcon className="w-8 h-8 mx-auto mb-2 text-amber-400" />
                    <p className="text-sm">Preview visual unavailable</p>
                  </div>
                )}

                {/* Top Badge */}
                <div className="absolute top-3 left-3 bg-slate-900/80 backdrop-blur-md px-2.5 py-1 rounded-full text-[11px] font-semibold text-emerald-300 border border-slate-700/50 flex items-center gap-1.5 shadow-xs">
                  <SparklesIcon className="w-3 h-3 text-emerald-400" />
                  <span>AI Generated Try-On</span>
                </div>

                {/* Bottom Disclaimer */}
                <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-slate-950/90 via-slate-950/60 to-transparent p-3 pt-6 text-center">
                  <p className="text-xs text-white font-bold">{product.name} • <span className="text-indigo-300">{product.color || 'Standard'}</span></p>
                  <p className="text-[10px] text-slate-300/90 font-medium mt-0.5">
                    FASHN VTON v1.5 Neural Synthesis • {product.brand || 'Apex'}
                  </p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                <Button
                  onClick={() => onAddToCart && onAddToCart(product.id)}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold py-2.5 flex items-center justify-center gap-1.5 shadow-md cursor-pointer"
                >
                  <ShoppingBagIcon className="w-3.5 h-3.5" /> Add to Cart
                </Button>
                <Button
                  variant="outline"
                  onClick={() => handleTabSwitch('camera')}
                  className="text-xs font-semibold py-2.5 flex items-center justify-center gap-1 text-slate-700 border-slate-300 hover:bg-slate-50 cursor-pointer"
                >
                  <RefreshCwIcon className="w-3.5 h-3.5" /> Try Again
                </Button>
                <Button
                  variant="outline"
                  onClick={() => handleTabSwitch('photo')}
                  className="text-xs font-semibold py-2.5 flex items-center justify-center gap-1 text-slate-700 border-slate-300 hover:bg-slate-50 cursor-pointer"
                >
                  <UploadIcon className="w-3.5 h-3.5" /> Change Photo
                </Button>
                <Button
                  variant="outline"
                  onClick={onClose}
                  className="text-xs font-semibold py-2.5 flex items-center justify-center gap-1 text-slate-700 border-slate-300 hover:bg-slate-50 cursor-pointer"
                >
                  Back to Product
                </Button>
              </div>

              {/* Complete the Look Section */}
              {jobData.complete_the_look && jobData.complete_the_look.length > 0 && (
                <div className="pt-3 border-t border-slate-100 space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                      <SparklesIcon className="w-3.5 h-3.5 text-indigo-600" /> Complete the Look
                    </h4>
                    <span className="text-[11px] text-slate-500">Matched styling recommendations</span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {jobData.complete_the_look.map((rec) => (
                      <div
                        key={rec.product_id}
                        className="p-2.5 rounded-xl border border-slate-200 bg-slate-50/50 hover:bg-slate-50 transition-all flex flex-col justify-between"
                      >
                        <div>
                          <div className="aspect-square rounded-lg bg-white overflow-hidden mb-2 border border-slate-100 relative">
                            <ProductImage
                              src={rec.image_url}
                              alt={rec.name}
                              productId={rec.product_id}
                              productName={rec.name}
                              className="w-full h-full object-cover"
                              containerClassName="w-full h-full"
                            />
                          </div>
                          <p className="text-[11px] font-bold text-slate-900 line-clamp-1">{rec.name}</p>
                          <p className="text-[11px] font-semibold text-indigo-600">₹{rec.price.toLocaleString('en-IN')}</p>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => onSelectProductToTry && onSelectProductToTry(rec.product_id)}
                          className="w-full mt-2 text-[10px] py-1 h-7 border-indigo-200 text-indigo-700 hover:bg-indigo-50 cursor-pointer"
                        >
                          Try This On
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STATE: ERROR */}
          {modalState === 'error' && (
            <div className="py-8 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 mx-auto flex items-center justify-center border border-rose-200">
                <AlertTriangleIcon className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-slate-900">Virtual Try-On Unavailable</h4>
                <p className="text-xs text-slate-600 max-w-sm mx-auto">
                  {errorMessage || 'We were unable to synthesize a preview. You can still purchase this product normally.'}
                </p>
              </div>
              <div className="flex justify-center gap-2.5 pt-2">
                <Button variant="outline" onClick={() => handleTabSwitch('camera')} className="text-xs">
                  Try Live Camera
                </Button>
                <Button onClick={() => fileInputRef.current?.click()} className="bg-indigo-600 text-white text-xs">
                  Upload Different Photo
                </Button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
