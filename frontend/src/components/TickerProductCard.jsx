import React, { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import useSpeechSynthesis from '../../hooks/useSpeechSynthesis';

export const TickerProductCard = ({
  product,
  onAddToCart,
  onQuickView,
  isAutoScrolling = true,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const [isAddAnimating, setIsAddAnimating] = useState(false);
  const { announceProduct, isPlaying } = useSpeechSynthesis();

  const handleAddClick = useCallback((e) => {
    e.stopPropagation();
    setIsAddAnimating(true);
    setTimeout(() => setIsAddAnimating(false), 600);
    
    if (onAddToCart) {
      onAddToCart(product);
    }
  }, [product, onAddToCart]);

  const handleQuickViewClick = useCallback((e) => {
    e.stopPropagation();
    if (onQuickView) {
      onQuickView(product);
    }
  }, [product, onQuickView]);

  const handleSpeakClick = useCallback((e) => {
    e.stopPropagation();
    announceProduct(product, 'en-IN');
  }, [product, announceProduct]);

  return (
    <motion.div
      className="flex-shrink-0 w-52 h-72 rounded-2xl overflow-hidden backdrop-blur-xl relative group"
      style={{
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.7) 0%, rgba(30, 41, 59, 0.6) 100%)',
        border: '1px solid rgba(34, 211, 238, 0.2)',
      }}
      whileHover={{ scale: 1.05 }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Glow Effect */}
      {isHovered && (
        <motion.div
          className="absolute inset-0 rounded-2xl pointer-events-none"
          style={{
            background: 'radial-gradient(circle at center, rgba(34, 211, 238, 0.1) 0%, transparent 70%)',
            boxShadow: '0 0 30px rgba(34, 211, 238, 0.4), inset 0 0 30px rgba(34, 211, 238, 0.1)',
          }}
          animate={{
            boxShadow: [
              '0 0 20px rgba(34, 211, 238, 0.2), inset 0 0 20px rgba(34, 211, 238, 0.1)',
              '0 0 40px rgba(34, 211, 238, 0.4), inset 0 0 30px rgba(34, 211, 238, 0.2)',
              '0 0 20px rgba(34, 211, 238, 0.2), inset 0 0 20px rgba(34, 211, 238, 0.1)',
            ],
          }}
          transition={{ duration: 2, repeat: Infinity }}
        />
      )}

      {/* Product Image Container */}
      <div className="relative h-40 overflow-hidden bg-gradient-to-br from-slate-800 to-slate-900">
        {product.image ? (
          <motion.img
            src={product.image}
            alt={product.name}
            className="w-full h-full object-cover"
            animate={isHovered ? { scale: 1.15 } : { scale: 1 }}
            transition={{ duration: 0.4 }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-slate-700 text-slate-400">
            <span className="text-sm">No Image</span>
          </div>
        )}

        {/* Shine Effect */}
        {isHovered && (
          <motion.div
            className="absolute inset-0 pointer-events-none"
            style={{
              background: 'linear-gradient(45deg, transparent 30%, rgba(255, 255, 255, 0.1) 50%, transparent 70%)',
              backgroundPosition: '0 0',
              backgroundSize: '200% 100%',
            }}
            animate={{ backgroundPosition: ['0 0', '200% 0'] }}
            transition={{ duration: 1.5 }}
          />
        )}

        {/* Discount Badge */}
        {product.discount_percent > 0 && (
          <motion.div
            className="absolute top-2 right-2 bg-gradient-to-r from-orange-500 to-red-600 text-white px-3 py-1 rounded-lg font-bold text-sm"
            animate={isHovered ? { scale: 1.1, rotate: 5 } : { scale: 1, rotate: 0 }}
            transition={{ duration: 0.3 }}
          >
            -{product.discount_percent}%
          </motion.div>
        )}

        {/* Category Badge */}
        <div className="absolute top-2 left-2 bg-cyan-500/20 backdrop-blur-sm text-cyan-200 px-2 py-1 rounded-lg text-xs font-semibold">
          {product.category || 'Product'}
        </div>
      </div>

      {/* Content Section */}
      <div className="flex flex-col flex-1 p-3 justify-between">
        {/* Product Name */}
        <div>
          <h3 className="font-bold text-white text-sm line-clamp-2 group-hover:text-cyan-300 transition-colors">
            {product.name}
          </h3>

          {/* Price Display */}
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-lg font-bold text-cyan-400">₹{product.price}</span>
            {product.mrp && product.mrp !== product.price && (
              <span className="text-xs text-slate-500 line-through">₹{product.mrp}</span>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 pt-2">
          {/* Speak Button */}
          <motion.button
            onClick={handleSpeakClick}
            disabled={isPlaying()}
            className="flex-1 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 disabled:opacity-50 text-white text-xs font-semibold transition-all"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            🔊 Speak
          </motion.button>

          {/* Add Button */}
          <motion.button
            onClick={handleAddClick}
            className="flex-1 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white text-xs font-semibold transition-all"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            animate={isAddAnimating ? { scale: [1, 0.9, 1.1, 1] } : {}}
          >
            + Add
          </motion.button>
        </div>

        {/* Quick View */}
        <motion.button
          onClick={handleQuickViewClick}
          className="w-full mt-2 py-1.5 text-xs text-cyan-300 hover:text-cyan-200 border border-cyan-400/30 hover:border-cyan-400/60 rounded-lg transition-colors"
          whileHover={{ backgroundColor: 'rgba(34, 211, 238, 0.05)' }}
        >
          👁 Quick View
        </motion.button>
      </div>

      {/* Floating Animation on Hover */}
      {isHovered && (
        <motion.div
          className="absolute -top-2 -right-2 w-12 h-12 bg-cyan-400/20 rounded-full blur-xl pointer-events-none"
          animate={{
            y: [-5, 5, -5],
            x: [-5, 5, -5],
          }}
          transition={{ duration: 3, repeat: Infinity }}
        />
      )}
    </motion.div>
  );
};

export default TickerProductCard;
