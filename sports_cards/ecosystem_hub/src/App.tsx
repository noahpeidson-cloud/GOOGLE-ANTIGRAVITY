import React, { useState, useEffect } from 'react';
// import { invoke } from '@tauri-apps/api/core';

export default function App() {
  const [cards, setCards] = useState([]);

  useEffect(() => {
    // Scaffold: Fetch from SQLite via Tauri backend
    setCards([
      { id: 1, player: 'Anthony Edwards', set: 'Prizm', year: '2020', grade: 'PSA 10' }
    ]);
  }, []);

  const handleExport = () => {
    console.log("Compiling Card Ladder CSV...");
    // invoke('export_card_ladder_csv');
  };

  return (
    <div className="p-4 bg-slate-900 text-white min-h-screen">
      <h1 className="text-3xl font-bold mb-4">Sports Card Ecosystem Hub</h1>
      <button 
        onClick={handleExport}
        className="mb-4 bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-4 rounded"
      >
        Export Card Ladder CSV
      </button>
      
      <table className="min-w-full bg-slate-800">
        <thead>
          <tr>
            <th className="py-2 px-4 border-b">Player</th>
            <th className="py-2 px-4 border-b">Set</th>
            <th className="py-2 px-4 border-b">Year</th>
            <th className="py-2 px-4 border-b">Grade</th>
          </tr>
        </thead>
        <tbody>
          {cards.map(card => (
            <tr key={card.id} className="text-center">
              <td className="py-2 px-4 border-b">{card.player}</td>
              <td className="py-2 px-4 border-b">{card.set}</td>
              <td className="py-2 px-4 border-b">{card.year}</td>
              <td className="py-2 px-4 border-b">{card.grade}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
