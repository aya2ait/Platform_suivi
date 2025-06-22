// src/App.jsx

import React, { useState } from 'react';
import Header from './components/common/Header';
import MissionsList from './components/missions/MissionsList';
import CollaborateursTab from './components/placeholders/CollaborateursTab';
import VehiculesTab from './components/placeholders/VehiculesTab';
import RapportsTab from './components/placeholders/RapportsTab';

// Main App
const App = () => {
  const [activeTab, setActiveTab] = useState('missions');

  const renderContent = () => {
    switch (activeTab) {
      case 'missions':
        return <MissionsList />;
      case 'collaborateurs':
        return <CollaborateursTab />;
      case 'vehicules':
        return <VehiculesTab />;
      case 'rapports':
        return <RapportsTab />;
      default:
        return <MissionsList />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header activeTab={activeTab} setActiveTab={setActiveTab} />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {renderContent()}
      </main>
    </div>
  );
};

export default App;