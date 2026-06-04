import React, { useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import useSpeechSynthesis from '../hooks/useSpeechSynthesis';

export const QuickViewModal = ({
  product,
  isOpen,
  onClose,
  onAddToCart,
}) => {
  const { announceProduct } = useSpeechSynthesis();

  const handleAddClick = useCallback(() => {
    if (onAddToCart) {
      onAddToCart(product);
    }
    onClose();
  }, [product, onAddToCart, onClose]);

  const handleSpeakClick = useCallback(() => {
    announceProduct(product, 'en-IN');
  }, [product, announceProduct]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          />

          {/* Modal */}
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={onClose}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.3 }}
          >
            <motion.div
              className="w-full max-w-2xl rounded-3xl overflow-hidden"
              style={{
                background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.9) 100%)',
                border: '2px solid rgba(34, 211, 238, 0.3)',
                boxShadow: '0 0 60px rgba(34, 211, 238, 0.2), 0 20px 60px rgba(0, 0, 0, 0.5)',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Close Button */}
              <motion.button
                onClick={onClose}
                className="absolute top-6 right-6 z-10 w-10 h-10 rounded-full bg-cyan-500/20 hover:bg-cyan-500/40 border border-cyan-400/30 hover:border-cyan-400/60 flex items-center justify-center text-white text-xl transition-all"
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
              >
                ✕
              </motion.button>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 p-8">
                {/* Product Image */}
                <motion.div
                  className="flex items-center justify-center rounded-2xl overflow-hidden bg-gradient-to-br from-slate-800 to-slate-900 h-96"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: 0.1 }}
                >
                  {product.image ? (
                    <motion.img
                      src={product.image}
                      alt={product.name}
                      className="w-full h-full object-cover"
                      whileHover={{ scale: 1.1 }}
                      transition={{ duration: 0.4 }}
                    />
                  ) : (
                    <div className="flex items-center justify-center text-slate-400">
                      <span>No Image Available</span>
                    </div>
                  )}
                </motion.div>

                {/* Product Details */}
                <motion.div
                  className="flex flex-col justify-between"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: 0.2 }}
                >
                  {/* Category & Name */}
                  <div>
                    <div className="inline-block bg-cyan-500/20 backdrop-blur-sm text-cyan-300 px-3 py-1 rounded-lg text-xs font-semibold mb-4">
                      {product.category || 'Product'}
                    </div>

                    <h2 className="text-3xl font-bold text-white mb-4">
                      {product.name}
                    </h2>

                    {/* Price Section */}
                    <div className="mb-6">
                      <div className="flex items-end gap-4 mb-2">
                        <span className="text-4xl font-bold text-cyan-400">
                          ₹{product.price}
                        </span>
                        {product.mrp && product.mrp !== product.price && (
                          <span className="text-lg text-slate-400 line-through mb-1">
                            ₹{product.mrp}
                          </span>
                        )}
                      </div>

                      {product.discount_percent > 0 && (
                        <motion.div
                          className="inline-block bg-gradient-to-r from-orange-500 to-red-600 text-white px-4 py-2 rounded-lg font-bold"
                          animate={{ scale: [1, 1.05, 1] }}
                          transition={{ duration: 2, repeat: Infinity }}
                        >
                          Save {product.discount_percent}% 🎉
                        </motion.div>
                      )}
                    </div>

                    {/* SKU */}
                    <div className="mb-6 text-slate-400 text-sm">
                      <p className="font-semibold text-slate-300">SKU:</p>
                      <p className="font-mono text-cyan-300">{product.sku}</p>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="space-y-3">
                    {/* Speak Button */}
                    <motion.button
                      onClick={handleSpeakClick}
                      className="w-full py-3 px-6 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-semibold transition-all flex items-center justify-center gap-2"
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <span>🔊</span>
                      <span>Hear Product Details</span>
                    </motion.button>

                    {/* Add Button */}
                    <motion.button
                      onClick={handleAddClick}
                      className="w-full py-3 px-6 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold transition-all flex items-center justify-center gap-2"
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <span>🛒</span>
                      <span>Add to Cart</span>
                    </motion.button>

                    {/* Close Button */}
                    <motion.button
                      onClick={onClose}
                      className="w-full py-3 px-6 rounded-xl border-2 border-cyan-400/30 hover:border-cyan-400/60 text-cyan-300 hover:text-cyan-200 font-semibold transition-all"
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      Continue Shopping
                    </motion.button>
                  </div>
                </motion.div>
              </div>
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default QuickViewModal;
