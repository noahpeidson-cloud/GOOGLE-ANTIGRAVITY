import { useState, useEffect, useCallback } from 'react';
import {
  ConnectorConfig,
  DataConnect,
  getDataConnect,
  queryRef,
  mutationRef,
  executeQuery,
  executeMutation,
  QueryRef,
  MutationRef,
  QueryResult,
  MutationResult,
} from 'firebase/data-connect';

// =============================================================================
// Firebase Data Connect SDK Configuration
// Generated for connector: omnichannel-connector
// Service: omnichannel-service (location: us-central1)
// =============================================================================

export const connectorConfig: ConnectorConfig = {
  connector: 'omnichannel-connector',
  service: 'omnichannel-service',
  location: 'us-central1',
};

// =============================================================================
// Data Types & Operation Contracts (PostgreSQL / GraphQL)
// =============================================================================

export interface VideoTag {
  id: string; // Int64 mapped to string in JS/TS
  filename: string;
  filepath: string;
  domain: string;
  entity: string;
  viralFeatures: Record<string, unknown> | unknown[] | unknown;
  technical: Record<string, unknown> | unknown[] | unknown;
  createdAt: string;
  updatedAt: string;
}

export interface ListVideoTagsData {
  videoTags: VideoTag[];
}

export interface ListVideoTagsVariables {
  limit?: number;
  offset?: number;
}

export interface GetVideoTagData {
  videoTag?: VideoTag | null;
}

export interface GetVideoTagVariables {
  id: string;
}

export interface CreateVideoTagData {
  videoTag_insert: {
    id: string;
  };
}

export interface CreateVideoTagVariables {
  filename: string;
  filepath: string;
  domain: string;
  entity: string;
  viralFeatures: Record<string, unknown> | unknown[] | unknown;
  technical: Record<string, unknown> | unknown[] | unknown;
}

// Initial fallback mock data for offline/unconnected emulator resilience
export const INITIAL_OFFLINE_VIDEO_TAGS: VideoTag[] = [
  {
    id: '1',
    filename: '20260819_213606.mp4',
    filepath: '/sdcard/DCIM/Camera/20260819_213606.mp4',
    domain: 'EDM_FESTIVALS',
    entity: 'Excision',
    viralFeatures: {
      visualHooks: ['Mainstage Lasers', 'Paradox Visuals', 'Bass Drop'],
      energyLevel: 'Maximum',
      crowdReaction: 'Moshpit',
    },
    technical: {
      resolution: '3840x2160',
      fps: 60,
      codec: 'h264',
      bitrateKbps: 48000,
      audioClipping: false,
    },
    createdAt: '2026-08-19T21:36:06Z',
    updatedAt: '2026-08-19T21:36:06Z',
  },
  {
    id: '2',
    filename: '20260820_142210.mp4',
    filepath: '/sdcard/DCIM/Camera/20260820_142210.mp4',
    domain: 'SPORTS_CARDS',
    entity: '1986 Fleer Michael Jordan #57 PSA 10',
    viralFeatures: {
      visualHooks: ['Gem Mint Holo', 'UV Blacklight Test', 'Corner Centering 50/50'],
      estimatedValue: '$250,000',
    },
    technical: {
      resolution: '3840x2160',
      fps: 60,
      codec: 'h264',
      bitrateKbps: 52000,
      audioClipping: false,
    },
    createdAt: '2026-08-20T14:22:10Z',
    updatedAt: '2026-08-20T14:22:10Z',
  },
  {
    id: '3',
    filename: '20260821_194533.mp4',
    filepath: '/sdcard/DCIM/Camera/20260821_194533.mp4',
    domain: 'EDM_FESTIVALS',
    entity: 'Subtronics (Cyclops Dome 2026)',
    viralFeatures: {
      visualHooks: ['Double Drop', 'Tesseract Pyro', 'Fakeout VIP'],
      energyLevel: 'Extreme',
    },
    technical: {
      resolution: '3840x2160',
      fps: 60,
      codec: 'hevc',
      bitrateKbps: 60000,
      audioClipping: false,
    },
    createdAt: '2026-08-21T19:45:33Z',
    updatedAt: '2026-08-21T19:45:33Z',
  },
];

// =============================================================================
// Query & Mutation Ref Constructors
// =============================================================================

export function listVideoTagsRef(
  dc?: DataConnect,
  vars?: ListVideoTagsVariables
): QueryRef<ListVideoTagsData, ListVideoTagsVariables> {
  const dcInstance = dc || getDataConnect(connectorConfig);
  if (vars !== undefined) {
    return queryRef<ListVideoTagsData, ListVideoTagsVariables>(
      dcInstance,
      'ListVideoTags',
      vars
    );
  }
  return queryRef<ListVideoTagsData>(
    dcInstance,
    'ListVideoTags'
  ) as unknown as QueryRef<ListVideoTagsData, ListVideoTagsVariables>;
}

export function getVideoTagRef(
  vars: GetVideoTagVariables,
  dc?: DataConnect
): QueryRef<GetVideoTagData, GetVideoTagVariables> {
  const dcInstance = dc || getDataConnect(connectorConfig);
  return queryRef<GetVideoTagData, GetVideoTagVariables>(
    dcInstance,
    'GetVideoTag',
    vars
  );
}

export function createVideoTagRef(
  vars: CreateVideoTagVariables,
  dc?: DataConnect
): MutationRef<CreateVideoTagData, CreateVideoTagVariables> {
  const dcInstance = dc || getDataConnect(connectorConfig);
  return mutationRef<CreateVideoTagData, CreateVideoTagVariables>(
    dcInstance,
    'CreateVideoTag',
    vars
  );
}

// =============================================================================
// Action Execution Functions
// =============================================================================

export async function listVideoTags(
  dc?: DataConnect,
  vars?: ListVideoTagsVariables
): Promise<QueryResult<ListVideoTagsData, ListVideoTagsVariables>> {
  return executeQuery(listVideoTagsRef(dc, vars));
}

export async function getVideoTag(
  vars: GetVideoTagVariables,
  dc?: DataConnect
): Promise<QueryResult<GetVideoTagData, GetVideoTagVariables>> {
  return executeQuery(getVideoTagRef(vars, dc));
}

export async function createVideoTag(
  vars: CreateVideoTagVariables,
  dc?: DataConnect
): Promise<MutationResult<CreateVideoTagData, CreateVideoTagVariables>> {
  return executeMutation(createVideoTagRef(vars, dc));
}

// =============================================================================
// Reactive React Hooks with Resilient Emulator/Offline Fallback
// =============================================================================

export interface UseVideoTagsResult {
  tags: VideoTag[];
  loading: boolean;
  error: Error | null;
  isOfflineFallback: boolean;
  refetch: () => Promise<void>;
  addTag: (vars: CreateVideoTagVariables) => Promise<boolean>;
}

export function useVideoTags(
  dc?: DataConnect,
  vars?: ListVideoTagsVariables
): UseVideoTagsResult {
  const [tags, setTags] = useState<VideoTag[]>(INITIAL_OFFLINE_VIDEO_TAGS);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [isOfflineFallback, setIsOfflineFallback] = useState<boolean>(false);

  const fetchTags = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listVideoTags(dc, vars);
      if (result?.data?.videoTags) {
        setTags(result.data.videoTags);
        setIsOfflineFallback(false);
      } else {
        setTags(INITIAL_OFFLINE_VIDEO_TAGS);
        setIsOfflineFallback(true);
      }
    } catch (err) {
      console.warn('[Firebase Data Connect] Query fallback mode active:', err);
      setTags(INITIAL_OFFLINE_VIDEO_TAGS);
      setIsOfflineFallback(true);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [dc, vars]);

  useEffect(() => {
    let isMounted = true;
    const executeFetch = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await listVideoTags(dc, vars);
        if (!isMounted) return;
        if (result?.data?.videoTags) {
          setTags(result.data.videoTags);
          setIsOfflineFallback(false);
        } else {
          setTags(INITIAL_OFFLINE_VIDEO_TAGS);
          setIsOfflineFallback(true);
        }
      } catch (err) {
        if (!isMounted) return;
        console.warn('[Firebase Data Connect] Query fallback mode active:', err);
        setTags(INITIAL_OFFLINE_VIDEO_TAGS);
        setIsOfflineFallback(true);
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };
    executeFetch();
    return () => {
      isMounted = false;
    };
  }, [dc, vars]);

  const addTag = useCallback(
    async (newTagVars: CreateVideoTagVariables): Promise<boolean> => {
      try {
        await createVideoTag(newTagVars, dc);
        await fetchTags();
        return true;
      } catch (err) {
        console.warn('[Firebase Data Connect] Mutation local fallback:', err);
        // Optimistic local fallback update
        const optimisticTag: VideoTag = {
          id: String(Date.now()),
          filename: newTagVars.filename,
          filepath: newTagVars.filepath,
          domain: newTagVars.domain,
          entity: newTagVars.entity,
          viralFeatures: newTagVars.viralFeatures,
          technical: newTagVars.technical,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        setTags((prev) => [optimisticTag, ...prev]);
        return true;
      }
    },
    [dc, fetchTags]
  );

  return {
    tags,
    loading,
    error,
    isOfflineFallback,
    refetch: fetchTags,
    addTag,
  };
}
