import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Initialize RevitPy bridge for WebView communication
if (typeof window !== 'undefined' && !window.revitpy) {
  window.revitpy = {
    // Message handling
    receiveMessage: (message: any) => {
      window.dispatchEvent(new CustomEvent('revitpy:message', { detail: message }));
    },

    // Send message to host
    sendMessage: (message: any) => {
      if (window.chrome?.webview) {
        window.chrome.webview.postMessage(JSON.stringify(message));
      } else {
        console.warn('RevitPy WebView bridge not available');
      }
    },

    // Development mode flag
    dev: import.meta.env.DEV,

    // Hot reload support
    hotReload: import.meta.env.DEV,
  };
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
