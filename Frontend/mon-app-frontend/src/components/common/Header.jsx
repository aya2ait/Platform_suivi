// src/components/common/Header.jsx - Version debug
import React from 'react';
import { useAuth } from '../../contexts/AuthContext';

const Header = ({ activeTab, setActiveTab, availableTabs }) => {
    const { user, logout } = useAuth();

    console.log('=== HEADER RENDER ===');
    console.log('Available tabs:', availableTabs);
    console.log('Active tab:', activeTab);
    console.log('setActiveTab function:', typeof setActiveTab);

    const handleTabClick = (tabId) => {
        console.log('=== TAB CLICKED ===');
        console.log('Clicked tab:', tabId);
        console.log('Current active:', activeTab);
        
        if (typeof setActiveTab === 'function') {
            setActiveTab(tabId);
            console.log('setActiveTab called with:', tabId);
        } else {
            console.log('❌ setActiveTab is not a function:', typeof setActiveTab);
        }
    };

    const handleLogout = () => {
        console.log('Logout clicked');
        logout();
    };

    return (
        <header className="bg-white shadow-lg border-b border-gray-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center py-4">
                    {/* Logo/Title */}
                    <div className="flex items-center">
                        <h1 className="text-2xl font-bold text-gray-900">
                            Gestion des Missions
                        </h1>
                    </div>

                    {/* User Info */}
                    <div className="flex items-center space-x-4">
                        <span className="text-sm text-gray-600">
                            {user?.nom} ({user?.role})
                        </span>
                        <button
                            onClick={handleLogout}
                            className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
                        >
                            Déconnexion
                        </button>
                    </div>
                </div>

                {/* Navigation Tabs */}
                <div className="border-b border-gray-200">
                    <nav className="-mb-px flex space-x-8">
                        {availableTabs.map((tab) => {
                            const isActive = activeTab === tab.id;
                            console.log(`Tab ${tab.id}: active=${isActive}`);
                            
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => handleTabClick(tab.id)}
                                    className={`
                                        py-2 px-1 border-b-2 font-medium text-sm transition-colors cursor-pointer
                                        ${isActive
                                            ? 'border-blue-500 text-blue-600 bg-blue-50'
                                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                        }
                                    `}
                                    style={{ minWidth: '100px' }}
                                >
                                    {tab.name}
                                </button>
                            );
                        })}
                    </nav>
                </div>
            </div>
        </header>
    );
};

export default Header;