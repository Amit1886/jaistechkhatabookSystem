import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import TickerProductCard from './TickerProductCard';
import QuickViewModal from './QuickViewModal';
import useLiveProductFeed from '../hooks/useLiveProductFeed';

export const LiveProductTicker = ({ onAddToCart, sessionKey }) => {
  const { products, loading, error } = useLiveProductFeed();
  const [displayProducts, setDisplayProducts] = useState([]);
  const [scrollX, setScrollX] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  const containerRef = useRef(null);
  const scrollerRef = useRef(null);
  const animationFrameRef = useRef(null);
  const lastScrollRef = useRef(0);
  const directionRef = useRef('left'); // Direction of scroll
  
  // Scroll speed in pixels per frame (60fps = ~2 pixels per frame for smooth scroll)
  const SCROLL_SPEED = 2;
  const CARD_WIDTH = 220; // 52 (w-52) * 4 + gaps
  const GAP = 16;

  // Initialize display products with cloning for infinite effect
  useEffect(() => {
    if (products.length > 0) {
      // Clone products 3x to create seamless infinite loop
      const cloned = [...products, ...products, ...products];
      setDisplayProducts(cloned);
      setScrollX(0);
      lastScrollRef.current = 0;
    }
  }, [products]);

  // Auto-scroll animation
  useEffect(() => {
    if (isPaused || displayProducts.length === 0 || loading) return;

    const animate = () => {
      setScrollX((prev) => {
        let newScroll = prev + SCROLL_SPEED;
        const singleSetWidth = products.length * (CARD_WIDTH + GAP);
        const totalWidth = singleSetWidth * 3;

        // Reset to seamless loop
        if (newScroll >= singleSetWidth) {
          newScroll = 0;
        }

        lastScrollRef.current = newScroll;
        return newScroll;
      });

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    animationFrameRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPaused, displayProducts.length, products.length, loading]);

  // Handle mouse interactions
  const handleMouseEnter = useCallback(() => {
    setIsPaused(true);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setIsPaused(false);
  }, []);

  // Touch/drag support
  const handleTouchStart = useRef(0);
  const handleTouchEnd = useRef(0);

  const handleTouchStartEvent = (e) => {
    handleTouchStart.current = e.touches[0].clientX;
    setIsPaused(true);
  };

  const handleTouchEndEvent = (e) => {
    handleTouchEnd.current = e.changedTouches[0].clientX;
    const diff = handleTouchStart.current - handleTouchEnd.current;
    
    if (Math.abs(diff) > 50) {
      // Significant drag detected
      if (diff > 0) {
        // Dragged left - move ticker right (scroll left in direction)
        setScrollX((prev) => Math.max(prev - 100, 0));
      } else {
        // Dragged right - move ticker left (scroll right in direction)
        const maxScroll = products.length * (CARD_WIDTH + GAP);
        setScrollX((prev) => Math.min(prev + 100, maxScroll));
      }
    }
    
    // Resume auto-scroll after 1 second
    setTimeout(() => setIsPaused(false), 1000);
  };

  const handleAddToCart = useCallback((product) => {
    if (onAddToCart) {
      onAddToCart(product, sessionKey);
    }
  }, [onAddToCart, sessionKey]);

  const handleQuickView = useCallback((product) => {
    setSelectedProduct(product);
    setIsModalOpen(true);
  }, []);

  const handleModalClose = useCallback(() => {
    setIsModalOpen(false);
    setTimeout(() => setSelectedProduct(null), 300);
  }, []);

  if (loading && products.length === 0) {
    return (
      <div className="w-full h-72 flex items-center justify-center backdrop-blur-xl rounded-2xl"
        style={{
          background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.7) 0%, rgba(30, 41, 59, 0.6) 100%)',
          border: '1px solid rgba(34, 211, 238, 0.2)',
        }}
      >
        <div className="text-center">
          <div className="inline-block animate-spin mb-4">
            <div className="w-12 h-12 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full" />
          </div>
          <p className="text-cyan-300 font-semibold">Loading Live Products...</p>
        </div>
      </div>
    );
  }

  if (error || products.length === 0) {
    return (
      <div className="w-full h-72 flex items-center justify-center backdrop-blur-xl rounded-2xl"
        style={{
          background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.7) 0%, rgba(30, 41, 59, 0.6) 100%)',
          border: '1px solid rgba(34, 211, 238, 0.2)',
        }}
      >
        <div className="text-center">
          <p className="text-slate-400 font-semibold">No products available</p>
          <p className="text-slate-500 text-sm mt-2">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Ticker Container */}
      <motion.div
        ref={containerRef}
        className="w-full overflow-hidden rounded-2xl backdrop-blur-xl relative group"
        style={{
          background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.4) 0%, rgba(30, 41, 59, 0.3) 100%)',
          border: '2px solid rgba(34, 211, 238, 0.15)',
        }}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onTouchStart={handleTouchStartEvent}
        onTouchEnd={handleTouchEndEvent}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Background Gradient Overlay */}
        <div className="absolute inset-0 pointer-events-none bg-gradient-to-r from-slate-900/40 via-transparent to-slate-900/40" />

        {/* Title Bar */}
        <div className="relative px-6 py-3 border-b border-cyan-500/20 bg-gradient-to-r from-cyan-900/20 to-blue-900/20 backdrop-blur-sm">
          <motion.h2
            className="text-cyan-300 font-bold text-lg flex items-center gap-2"
            animate={{ opacity: [1, 0.8, 1] }}
            transition={{ duration: 3, repeat: Infinity }}
          >
            <span className="inline-block w-2 h-2 bg-cyan-400 rounded-full animate-pulse" />
            Live Product Showcase
            <span className="inline-block w-2 h-2 bg-cyan-400 rounded-full animate-pulse" />
          </motion.h2>
          
          {/* Status Indicator */}
          <div className="absolute right-6 top-1/2 -translate-y-1/2 text-xs text-slate-400">
            {isPaused ? '⏸ Paused' : '▶ Auto-scrolling'}
          </div>
        </div>

        {/* Scroller */}
        <div
          ref={scrollerRef}
          className="relative overflow-hidden p-4"
          style={{ height: '320px' }}
        >
          {/* Left Fade Gradient */}
          <div className="absolute left-0 top-0 bottom-0 w-16 bg-gradient-to-r from-black/40 to-transparent z-10 pointer-events-none" />
          
          {/* Right Fade Gradient */}
          <div className="absolute right-0 top-0 bottom-0 w-16 bg-gradient-to-l from-black/40 to-transparent z-10 pointer-events-none" />

          {/* Product Cards */}
          <motion.div
            className="flex gap-4"
            style={{
              transform: `translateX(-${scrollX}px)`,
              willChange: 'transform',
            }}
            transition={{ type: 'linear', duration: 0 }}
          >
            {displayProducts.map((product, index) => (
              <TickerProductCard
                key={`${product.id}-${index}`}
                product={product}
                onAddToCart={handleAddToCart}
                onQuickView={handleQuickView}
                isAutoScrolling={!isPaused}
              />
            ))}
          </motion.div>
        </div>

        {/* Bottom Status Bar */}
        <div className="relative px-6 py-3 border-t border-cyan-500/20 bg-gradient-to-r from-blue-900/20 to-cyan-900/20 backdrop-blur-sm flex justify-between items-center text-xs text-slate-400">
          <span>{displayProducts.length / 3} products in rotation</span>
          <span className="text-cyan-400 font-semibold">💡 Hover to pause • Touch to drag</span>
        </div>
      </motion.div>

      {/* Quick View Modal */}
      <QuickViewModal
        product={selectedProduct}
        isOpen={isModalOpen}
        onClose={handleModalClose}
        onAddToCart={handleAddToCart}
      />
    </>
  );
};

export default LiveProductTicker;
