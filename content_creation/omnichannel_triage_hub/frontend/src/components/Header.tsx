import React from 'react';

interface HeaderProps {
  adbStatus?: {
    text: string;
    isActive: boolean;
  };
  phoneLinkStatus?: {
    text: string;
    isActive: boolean;
  };
}

export const Header: React.FC<HeaderProps> = ({
  adbStatus = { text: 'Pulling (24.1 GB / 90.5 GB)', isActive: true },
  phoneLinkStatus = { text: 'Live Screen Capture Active', isActive: true },
}) => {
  return (
    <header
      role="banner"
      aria-label="Omnichannel Triage Hub Header"
      className="flex justify-between items-end mb-8 pb-4 border-b border-[var(--border)]"
    >
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2 text-[var(--foreground)]">Omnichannel Triage Hub</h1>
        <p className="text-[var(--muted-foreground)]">
          Visually verifying ADB, Google Takeout, and Live Phone Link streams.
        </p>
      </div>
      <div className="flex space-x-6" role="region" aria-label="System status indicators">
        {/* Status Badge 1: ADB Connection */}
        <div className="flex flex-col items-end">
          <span className="text-xs uppercase tracking-wider text-[var(--muted-foreground)] mb-1">
            ADB Connection
          </span>
          <div
            role="status"
            aria-label={`ADB Connection: ${adbStatus.text}`}
            className="flex items-center space-x-2 bg-green-500/10 text-green-400 px-3 py-1 rounded-full border border-green-500/20"
          >
            {adbStatus.isActive && (
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" aria-hidden="true" />
            )}
            <span className="text-sm font-semibold">{adbStatus.text}</span>
          </div>
        </div>

        {/* Status Badge 2: Windows Phone Link */}
        <div className="flex flex-col items-end">
          <span className="text-xs uppercase tracking-wider text-[var(--muted-foreground)] mb-1">
            Windows Phone Link
          </span>
          <div
            role="status"
            aria-label={`Windows Phone Link: ${phoneLinkStatus.text}`}
            className="flex items-center space-x-2 bg-blue-500/10 text-blue-400 px-3 py-1 rounded-full border border-blue-500/20"
          >
            {phoneLinkStatus.isActive && (
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" aria-hidden="true" />
            )}
            <span className="text-sm font-semibold">{phoneLinkStatus.text}</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
