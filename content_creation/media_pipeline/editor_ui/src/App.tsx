import React, { useState, useEffect } from 'react';
// import { invoke } from '@tauri-apps/api/core'; // Tauri backend bindings

export default function App() {
  const [mediaList, setMediaList] = useState([]);

  useEffect(() => {
    // Scaffold: Fetch from SQLite via Tauri backend
    // invoke('get_media').then(setMediaList);
    setMediaList([{ id: 1, path: 'file://C:/Mock/Video.mp4', tags: ['EDM', 'Laser'] }]);
  }, []);

  return (
    <div className="p-4 bg-gray-900 text-white min-h-screen">
      <h1 className="text-3xl font-bold mb-4">Desktop Media Editor UI (Zero Degradation)</h1>
      <div className="grid grid-cols-3 gap-4">
        {mediaList.map(media => (
          <div key={media.id} className="border border-gray-700 p-2 rounded">
            {/* Native HTML5 local video playback ensures zero compression */}
            <video src={media.path} controls className="w-full h-48 bg-black" />
            <div className="mt-2">
              {media.tags.map(tag => (
                <span key={tag} className="mr-2 text-sm bg-blue-600 px-2 rounded">#{tag}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
