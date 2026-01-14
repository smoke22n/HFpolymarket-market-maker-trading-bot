'use client';

import Header from '@/components/Header';
import KPICards from '@/components/KPICards';
import TabbedInterface from '@/components/TabbedInterface';

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        <Header />
        <KPICards />
        <TabbedInterface />
      </div>
    </div>
  );
}