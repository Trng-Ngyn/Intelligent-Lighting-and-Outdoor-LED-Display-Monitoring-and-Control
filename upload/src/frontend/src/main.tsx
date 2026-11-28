import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import App from './App'
const client=new QueryClient({defaultOptions:{queries:{retry:0,refetchOnWindowFocus:true},mutations:{retry:0}}})
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={client}><BrowserRouter><App/></BrowserRouter></QueryClientProvider></React.StrictMode>)
