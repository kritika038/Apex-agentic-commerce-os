'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { MicIcon, MicOffIcon, AlertTriangleIcon, SparklesIcon, RotateCcwIcon } from '@/components/ui/Icons';

export interface VoiceSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTranscript: (query: string) => void;
  initialLanguage?: 'en-IN' | 'hi-IN';
}

export function VoiceSearchModal({
  isOpen,
  onClose,
  onTranscript,
  initialLanguage = 'en-IN',
}: VoiceSearchModalProps) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [lang, setLang] = useState<'en-IN' | 'hi-IN'>(initialLanguage);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore
      }
      setIsListening(false);
    }
  }, []);

  const startListening = useCallback(() => {
    setError(null);
    setTranscript('');

    if (typeof window === 'undefined') return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setError('Voice recognition is not supported in this browser. Please type your query in the search bar.');
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = lang;
      recognition.interimResults = true;
      recognition.continuous = false;

      recognition.onstart = () => {
        setIsListening(true);
      };

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onresult = (event: any) => {
        const current = event.resultIndex;
        const text = event.results[current][0].transcript;
        setTranscript(text);
      };

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onerror = (event: any) => {
        setIsListening(false);
        if (event.error === 'not-allowed') {
          setError('Microphone access was denied. Please allow microphone permissions in your browser settings.');
        } else if (event.error === 'no-speech') {
          setError('No speech was detected. Please click Try Again and speak into your microphone.');
        } else {
          setError(`Voice input error: ${event.error}. Please try again.`);
        }
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error('Speech recognition error:', err);
      setError('Could not initialize microphone. Please check browser permissions.');
      setIsListening(false);
    }
  }, [lang]);

  useEffect(() => {
    if (isOpen) {
      startListening();
    } else {
      stopListening();
    }
    return () => {
      stopListening();
    };
  }, [isOpen, startListening, stopListening]);

  // Real-time intent interpretation preview
  const interpretedIntent = useMemo(() => {
    if (!transcript.trim()) return null;
    const lower = transcript.toLowerCase();
    
    // Category detection
    let cat = '';
    if (/shoe|jute|joote|jhoote|joota|sneaker|running|दौड़|जूते/i.test(lower)) cat = 'Running Shoes';
    else if (/bag|duffle|duffel|jhola|बस्ता|बैग/i.test(lower)) cat = 'Gym Bags';
    else if (/watch|tracker|ghadi|घड़ी/i.test(lower)) cat = 'Fitness Watch';
    else if (/shirt|tee|shorts|kapde|कपड़े/i.test(lower)) cat = 'Workout Apparel';
    else if (/bottle|pani|flask|बोतल/i.test(lower)) cat = 'Water Bottle';

    // Budget detection
    let budget = '';
    if (/5000|5k|pancho|pan su|paanch hazaar|panch hajar|पांच/i.test(lower)) budget = '₹5,000';
    else if (/3000|3k|teen hazaar|tin hajar|तीन/i.test(lower)) budget = '₹3,000';
    else if (/2000|2k|do hazaar|दो/i.test(lower)) budget = '₹2,000';
    else if (/1500|1\.5k|dedh|derh|डेढ़/i.test(lower)) budget = '₹1,500';
    else if (/600|che sau/i.test(lower)) budget = '₹600';
    else if (/500|paanch sau/i.test(lower)) budget = '₹500';

    if (cat && budget) return `${cat} up to ${budget}`;
    if (cat) return cat;
    if (budget) return `Products up to ${budget}`;
    return null;
  }, [transcript]);

  const handleConfirm = () => {
    if (transcript.trim()) {
      onTranscript(transcript.trim());
      onClose();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Voice Shopping Assistant" maxWidth="md">
      <div className="space-y-6 text-center py-2">
        {/* Language Selector */}
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setLang('en-IN')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-full transition-colors ${
              lang === 'en-IN'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            English (India)
          </button>
          <button
            onClick={() => setLang('hi-IN')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-full transition-colors ${
              lang === 'hi-IN'
                ? 'bg-slate-900 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            हिंदी (Hindi / Hinglish)
          </button>
        </div>

        {/* Pulse Microphone Ring */}
        <div className="relative w-24 h-24 mx-auto flex items-center justify-center">
          {isListening && (
            <div className="absolute inset-0 rounded-full bg-indigo-500/20 animate-ping" />
          )}
          <button
            onClick={isListening ? stopListening : startListening}
            className={`relative w-20 h-20 rounded-full flex items-center justify-center text-white shadow-lg transition-all ${
              isListening
                ? 'bg-rose-600 hover:bg-rose-700 scale-105'
                : 'bg-slate-900 hover:bg-indigo-600'
            }`}
            title={isListening ? 'Stop Listening' : 'Start Listening'}
            aria-label={isListening ? 'Stop Listening' : 'Start Listening'}
          >
            {isListening ? <MicIcon size={32} /> : <MicOffIcon size={32} />}
          </button>
        </div>

        {/* Status Text */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            {isListening
              ? lang === 'hi-IN'
                ? 'सुन रहे हैं... बोलिए (Listening in Hindi / Hinglish)'
                : 'Listening... Speak now'
              : 'Tap microphone to speak'}
          </p>

          <div className="min-h-14 flex flex-col items-center justify-center px-4 space-y-1">
            {transcript ? (
              <>
                <p className="text-sm font-semibold text-slate-900 italic">
                  &ldquo;{transcript}&rdquo;
                </p>
                {interpretedIntent && (
                  <div className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                    <SparklesIcon size={12} />
                    <span>Searching intent: <strong>{interpretedIntent}</strong></span>
                  </div>
                )}
              </>
            ) : (
              <p className="text-xs text-slate-400">
                {lang === 'hi-IN'
                  ? 'उदा: "5000 ke andar running shoes chahiye"'
                  : 'e.g. "Show running shoes under ₹5,000"'}
              </p>
            )}
          </div>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2 text-left">
            <AlertTriangleIcon size={16} className="text-rose-600 shrink-0" />
            <div className="flex-1">{error}</div>
            <button
              onClick={startListening}
              className="text-xs font-bold text-rose-700 underline shrink-0 hover:text-rose-900"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Modal Buttons */}
        <div className="flex items-center justify-between border-t border-slate-200 pt-4">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>

          <div className="flex items-center gap-2">
            {transcript && (
              <Button
                variant="secondary"
                size="sm"
                onClick={startListening}
                leftIcon={<RotateCcwIcon size={14} />}
              >
                Try Again
              </Button>
            )}
            <Button
              variant="primary"
              size="sm"
              onClick={handleConfirm}
              disabled={!transcript.trim()}
            >
              Search Catalog →
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
