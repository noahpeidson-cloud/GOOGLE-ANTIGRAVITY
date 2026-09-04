export interface AdbStatusState {
  connected: boolean;
  status: 'idle' | 'pulling' | 'completed' | 'error';
  progressText: string;
  bytesTransferred: number;
  totalBytes: number;
}

export interface PhoneLinkFeedState {
  active: boolean;
  currentVideo: {
    filename: string;
    description: string;
    src: string;
    poster: string;
  };
  visionResult: {
    entity: string;
    attribute: string;
    action: string;
    confidence?: number;
  };
}

export interface CollisionSource {
  title: string;
  resolution: string;
  resolutionSubtext: string;
  sourcePath: string;
  size: string;
  badgeColor: 'green' | 'red';
}

export interface CollisionItem {
  id: string;
  filename: string;
  timestamp: string;
  conflictType: string;
  adbSource: CollisionSource;
  takeoutSource: CollisionSource;
  resolved?: boolean;
  resolutionChoice?: 'adb' | 'takeout';
}
