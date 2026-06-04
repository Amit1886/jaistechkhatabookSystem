import React, { useState, useCallback } from "react";
import "../../styles/selfcheckout.css";
import LiveProductTicker from "../../components/LiveProductTicker";

/**
 * SmartKioskDemo - Main self-checkout kiosk component
 * Integrates live product ticker with existing kiosk UI
 */
export default function SmartKioskDemo() {
  const [cart, setCart] = useState([]);
  const [sessionKey, setSessionKey] = useState(null);

  // Handle adding product to cart
  const handleAddToCart = useCallback((product, sessionKey) => {
    console.log("Adding to cart:", product);
    setCart((prevCart) => {
      const existingItem = prevCart.find((item) => item.id === product.id);
      if (existingItem) {
        return prevCart.map((item) =>
          item.id === product.id ? { ...item, qty: item.qty + 1 } : item
        );
      }
      return [...prevCart, { ...product, qty: 1 }];
    });

    // Show visual feedback
    // TODO: Trigger cart animation
  }, []);

  return (
    <div className="w-full h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white overflow-hidden">
      {/* Header */}
      <header className="bg-gradient-to-r from-slate-900 to-slate-800 border-b border-cyan-500/20 px-8 py-4 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
            Smart Self Checkout
          </h1>
          <p className="text-cyan-300 text-sm mt-1">Live Product Showcase</p>
        </div>
        <div className="bg-cyan-600/20 border border-cyan-400/50 rounded-full px-6 py-2 text-cyan-300 font-semibold">
          User, DemoTest3
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden gap-4 p-4">
        {/* Left Section: Live Product Ticker */}
        <div className="flex-1 flex flex-col">
          <LiveProductTicker onAddToCart={handleAddToCart} sessionKey={sessionKey} />
        </div>

        {/* Right Section: Scan & Cart Area */}
        <div className="w-96 flex flex-col gap-4">
          {/* Live Cart */}
          <div
            className="flex-1 rounded-2xl overflow-hidden backdrop-blur-xl border"
            style={{
              background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.7) 0%, rgba(30, 41, 59, 0.6) 100%)',
              borderColor: 'rgba(34, 211, 238, 0.2)',
            }}
          >
            <div className="bg-gradient-to-r from-cyan-900/30 to-blue-900/30 backdrop-blur-sm border-b border-cyan-500/20 px-6 py-4">
              <h2 className="text-cyan-300 font-bold text-lg flex items-center gap-2">
                🛒 Live Cart
                <span className="ml-auto bg-cyan-600/50 text-cyan-200 px-3 py-1 rounded-full text-sm font-semibold">
                  {cart.length > 0 ? `${cart.length} Items` : "Empty"}
                </span>
              </h2>
            </div>

            <div className="overflow-y-auto p-4 space-y-3" style={{ maxHeight: 'calc(100% - 80px)' }}>
              {cart.length === 0 ? (
                <div className="flex items-center justify-center h-full text-slate-400 text-sm">
                  <p>Your cart is empty</p>
                </div>
              ) : (
                cart.map((item) => (
                  <div
                    key={item.id}
                    className="bg-slate-800/40 border border-cyan-500/20 rounded-lg p-3 flex justify-between items-center"
                  >
                    <div>
                      <p className="text-white font-semibold text-sm">{item.name}</p>
                      <p className="text-cyan-300 text-xs">Qty: {item.qty}</p>
                    </div>
                    <p className="text-cyan-400 font-bold">₹{item.price * item.qty}</p>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Scan & Pay Section */}
          <div
            className="rounded-2xl overflow-hidden backdrop-blur-xl border p-6 flex flex-col gap-4"
            style={{
              background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.7) 0%, rgba(30, 41, 59, 0.6) 100%)',
              borderColor: 'rgba(34, 211, 238, 0.2)',
            }}
          >
            <h2 className="text-cyan-300 font-bold text-lg">📱 Scan & Pay</h2>
            
            <div className="bg-white rounded-xl p-4 flex items-center justify-center">
              <div className="w-40 h-40 bg-gradient-to-br from-slate-200 to-slate-300 rounded-lg flex items-center justify-center">
                <svg
                  className="w-32 h-32 text-slate-400"
                  fill="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path d="M3 11h8V3H3v8zm0 8h8v-8H3v8zm10-8h8V3h-8v8zm0 8h8v-8h-8v8z" />
                </svg>
              </div>
            </div>

            <div className="space-y-2 text-center text-slate-400 text-xs">
              <p className="font-semibold text-cyan-300">QR Code Scanner Ready</p>
              <p>Scan QR code or tap card to pay</p>
            </div>

            <button className="w-full py-3 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold rounded-lg transition-all">
              💳 Complete Purchase
            </button>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-slate-900/50 border-t border-cyan-500/20 px-8 py-3 text-xs text-slate-500 flex justify-between">
        <span>Kiosk ID: KIOSK-1 | Status: Online</span>
        <span>v1.0.0 | © 2024 Smart Retail</span>
      </footer>
    </div>
  );
}