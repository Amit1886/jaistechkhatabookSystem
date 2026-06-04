import axios from "axios";

export const fetchLiveProducts = async () => {
  const response = await axios.get(
    "/selfcheckout/live-products/"
  );

  return response.data.products;
};