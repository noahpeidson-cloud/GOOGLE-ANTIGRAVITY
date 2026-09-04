import { initializeApp, getApps, getApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  projectId: "noahs-ai-bussin",
  appId: "1:551414926862:web:84170e2d84d452d163f65f",
  storageBucket: "noahs-ai-bussin.firebasestorage.app",
  apiKey: "AIzaSyAm2iQhnej19SBqoa3z9LojB-Wdm2qLTpU",
  authDomain: "noahs-ai-bussin.firebaseapp.com",
  messagingSenderId: "551414926862",
  measurementId: "G-Q9S1S7D5HT"
};

const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();
const db = getFirestore(app);

export { app, db };
