'use client';
import { useState, useEffect } from 'react';
import { db } from '@/lib/firebase';
import { collection, addDoc, query, orderBy, onSnapshot, limit } from 'firebase/firestore';

export default function Home() {
  const [logs, setLogs] = useState<{id: string, message: string}[]>([]);
  const [status, setStatus] = useState('idle');

  useEffect(() => {
    // Listen to the most recent command's logs
    const q = query(collection(db, 'logs'), orderBy('timestamp', 'desc'), limit(50));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const newLogs = snapshot.docs.map(doc => ({
        id: doc.id,
        message: doc.data().message,
        timestamp: doc.data().timestamp
      })).reverse();
      setLogs(newLogs);
    });
    return () => unsubscribe();
  }, []);

  const triggerPipeline = async () => {
    setStatus('processing');
    await addDoc(collection(db, 'commands'), {
      action: 'trigger_edm_pipeline',
      status: 'pending',
      timestamp: Date.now()
    });
  };

  return (
    <main className="min-h-screen bg-black text-green-500 p-8 font-mono">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-8 text-white">AGY Command Center</h1>
        
        <div className="mb-8">
          <button 
            onClick={triggerPipeline}
            disabled={status === 'processing'}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded border border-blue-400 disabled:opacity-50"
          >
            {status === 'processing' ? 'Pipeline Running...' : 'Trigger EDM Pipeline'}
          </button>
        </div>

        <div className="bg-gray-900 border border-gray-700 rounded p-4 h-96 overflow-y-auto shadow-2xl shadow-green-900/20">
          <h2 className="text-gray-400 text-sm mb-4 uppercase tracking-widest border-b border-gray-700 pb-2">Terminal Output</h2>
          {logs.map(log => (
            <div key={log.id} className="mb-1 opacity-90 hover:opacity-100">
              <span className="text-gray-500 mr-2">$</span>
              {log.message}
            </div>
          ))}
          {logs.length === 0 && <div className="text-gray-600 italic">Awaiting telemetry...</div>}
        </div>
      </div>
    </main>
  );
}
