import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 900,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: "react-vendor",
              test: /node_modules[\\/](react|react-dom|react-router-dom)[\\/]/,
            },
            {
              name: "antd-core",
              test: /node_modules[\\/]antd[\\/]/,
            },
            {
              name: "antd-icons",
              test: /node_modules[\\/]@ant-design[\\/]icons[\\/]/,
            },
            {
              name: "antd-support",
              test: /node_modules[\\/](@ant-design[\\/](colors|cssinjs|fast-color)|@rc-component|rc-)/,
            },
            {
              name: "visual-vendor",
              test: /node_modules[\\/](echarts|@xyflow|pdfjs-dist)[\\/]/,
            },
          ],
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});
