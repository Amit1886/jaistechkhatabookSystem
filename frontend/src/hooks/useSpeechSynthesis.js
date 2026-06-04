import { useCallback, useRef } from 'react';

export const useSpeechSynthesis = () => {
  const synthesisRef = useRef(null);
  const isPlayingRef = useRef(false);

  const speak = useCallback((text, language = 'en-IN', rate = 0.9) => {
    // Cancel any ongoing speech
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }

    if (!text || !text.trim()) return;

    try {
      const utterance = new SpeechSynthesisUtterance(text);
      
      // Set language
      if (language === 'hi' || language === 'hi-IN') {
        utterance.lang = 'hi-IN';
      } else {
        utterance.lang = 'en-IN';
      }
      
      // Optimized settings for kiosk
      utterance.rate = rate;
      utterance.pitch = 1.0;
      utterance.volume = 0.9;
      
      utterance.onstart = () => {
        isPlayingRef.current = true;
      };
      
      utterance.onend = () => {
        isPlayingRef.current = false;
      };
      
      utterance.onerror = (event) => {
        console.error('Speech synthesis error:', event.error);
        isPlayingRef.current = false;
      };
      
      synthesisRef.current = utterance;
      
      if ('speechSynthesis' in window) {
        window.speechSynthesis.speak(utterance);
      }
    } catch (error) {
      console.error('Error initializing speech synthesis:', error);
    }
  }, []);

  const stop = useCallback(() => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      isPlayingRef.current = false;
    }
  }, []);

  const isPlaying = () => isPlayingRef.current;

  // Build announcement text for product
  const announceProduct = useCallback((product, language = 'en-IN') => {
    if (!product) return;

    let announcement = '';
    
    if (language === 'hi' || language === 'hi-IN') {
      announcement = `${product.name}। कीमत है ${product.price} रुपये`;
      if (product.discount_percent > 0) {
        announcement += `। ${product.discount_percent} प्रतिशत छूट`;
      }
      announcement += '। खरीद बटन दबाएँ।';
    } else {
      announcement = `${product.name}. Price is ${product.price} rupees`;
      if (product.discount_percent > 0) {
        announcement += `. ${product.discount_percent} percent discount`;
      }
      announcement += `. Press the add button.`;
    }
    
    speak(announcement, language, 0.85);
  }, [speak]);

  return {
    speak,
    stop,
    isPlaying,
    announceProduct,
  };
};

export default useSpeechSynthesis;
