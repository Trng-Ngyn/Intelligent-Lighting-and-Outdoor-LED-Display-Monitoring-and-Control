import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './console/style.css';
import 'leaflet/dist/leaflet.css';
const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } } });
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><QueryClientProvider client={client}><App /></QueryClientProvider></React.StrictMode>
);
