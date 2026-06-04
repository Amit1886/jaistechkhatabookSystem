import { useState, useEffect, useRef } from 'react';

const API_ENDPOINT = '/pos/self-checkout/live-products/';
const CACHE_DURATION = 60000; // 60 seconds

export const useLiveProductFeed = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const cacheRef = useRef({ data: null, timestamp: 0 });
  const fetchTimeoutRef = useRef(null);

  const fetchProducts = async () => {
    try {
      setError(null);
      
      // Check cache first
      const now = Date.now();
      if (
        cacheRef.current.data &&
        now - cacheRef.current.timestamp < CACHE_DURATION
      ) {
        setProducts(cacheRef.current.data);
        setLoading(false);
        return;
      }

      const response = await fetch(API_ENDPOINT);
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.ok && data.products) {
        const productList = data.products;
        cacheRef.current = {
          data: productList,
          timestamp: now,
        };
        setProducts(productList);
        setError(null);
      } else {
        throw new Error('Invalid API response');
      }
    } catch (err) {
      console.error('Error fetching live products:', err);
      setError(err.message);
      
      // Fallback to empty array on error, but try again
      setProducts(cacheRef.current.data || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchProducts();

    // Optional: Refresh every 2 minutes for price updates
    const refreshInterval = setInterval(() => {
      fetchProducts();
    }, 120000);

    return () => {
      clearInterval(refreshInterval);
      if (fetchTimeoutRef.current) {
        clearTimeout(fetchTimeoutRef.current);
      }
    };
  }, []);

  return {
    products,
    loading,
    error,
    refetch: fetchProducts,
  };
};

export default useLiveProductFeed;
