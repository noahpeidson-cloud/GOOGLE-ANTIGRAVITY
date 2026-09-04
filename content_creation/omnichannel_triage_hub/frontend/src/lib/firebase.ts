import { initializeApp, getApps, getApp, FirebaseApp } from 'firebase/app';
import {
  getDataConnect,
  connectDataConnectEmulator,
  DataConnect,
} from 'firebase/data-connect';
import { connectorConfig } from './dataconnect';

// Firebase Web configuration (supports environment overrides)
export const firebaseConfig = {
  apiKey: (typeof import.meta !== 'undefined' && import.meta.env?.VITE_FIREBASE_API_KEY) || 'AIzaSyMockKeyForDevOnly_Omnichannel',
  authDomain: (typeof import.meta !== 'undefined' && import.meta.env?.VITE_FIREBASE_AUTH_DOMAIN) || 'omnichannel-triage.firebaseapp.com',
  projectId: (typeof import.meta !== 'undefined' && import.meta.env?.VITE_FIREBASE_PROJECT_ID) || 'omnichannel-triage',
  storageBucket: (typeof import.meta !== 'undefined' && import.meta.env?.VITE_FIREBASE_STORAGE_BUCKET) || 'omnichannel-triage.appspot.com',
  messagingSenderId: (typeof import.meta !== 'undefined' && import.meta.env?.VITE_FIREBASE_MESSAGING_SENDER_ID) || '123456789012',
  appId: (typeof import.meta !== 'undefined' && import.meta.env?.VITE_FIREBASE_APP_ID) || '1:123456789012:web:abcdef123456',
};

// Initialize or retrieve the singleton Firebase App instance
export const app: FirebaseApp =
  getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);

// Initialize Data Connect instance with omnichannel connector configuration
export const dataConnect: DataConnect = getDataConnect(app, connectorConfig);

// Connect to the Firebase Data Connect emulator in development or when explicitly enabled
const isDev = typeof import.meta !== 'undefined' && Boolean(import.meta.env?.DEV);
const useEmulator = typeof import.meta !== 'undefined' && import.meta.env?.VITE_USE_EMULATOR === 'true';

if (isDev || useEmulator) {
  const emulatorHost = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_DATA_CONNECT_EMULATOR_HOST) || 'localhost';
  const emulatorPort = Number((typeof import.meta !== 'undefined' && import.meta.env?.VITE_DATA_CONNECT_EMULATOR_PORT) || 9399);
  try {
    connectDataConnectEmulator(dataConnect, emulatorHost, emulatorPort);
    console.info(`[Firebase Data Connect] Connected to emulator at ${emulatorHost}:${emulatorPort}`);
  } catch (err) {
    console.warn('[Firebase Data Connect] Emulator connection warning:', err);
  }
}

export default dataConnect;
