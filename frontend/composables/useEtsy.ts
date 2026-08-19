import { ref } from 'vue';
import type {
  EtsyConnectResponse,
  EtsyConnectionStatus,
  EtsyDraftDispatchResponse,
} from '~/types/etsy';
import { getApiErrorMessage, getCsrfHeaders } from '~/utils/api';

export function useEtsy() {
  const config = useRuntimeConfig();
  const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, '') : '';

  const connectionStatus = ref<EtsyConnectionStatus | null>(null);
  const draftStatus = ref<EtsyDraftDispatchResponse | null>(null);
  const isLoading = ref(false);
  const isConnecting = ref(false);
  const isDisconnecting = ref(false);
  const isDispatching = ref(false);
  const errorMessage = ref<string | null>(null);

  async function fetchConnectionStatus(): Promise<EtsyConnectionStatus | null> {
    isLoading.value = true;
    errorMessage.value = null;
    try {
      const data = await $fetch<EtsyConnectionStatus>(`${apiBase}/api/v1/integrations/etsy`, {
        headers: { Accept: 'application/json' },
        credentials: 'include',
      });
      connectionStatus.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to fetch Etsy connection status.');
      return null;
    } finally {
      isLoading.value = false;
    }
  }

  async function initiateOAuthConnect(): Promise<string | null> {
    isConnecting.value = true;
    errorMessage.value = null;
    try {
      const data = await $fetch<EtsyConnectResponse>(`${apiBase}/api/v1/auth/etsy/connect`, {
        headers: { Accept: 'application/json' },
        credentials: 'include',
      });
      if (data?.authorization_url && typeof window !== 'undefined') {
        window.location.href = data.authorization_url;
      }
      return data.authorization_url;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to initiate Etsy OAuth connection.');
      return null;
    } finally {
      isConnecting.value = false;
    }
  }

  async function disconnectShop(): Promise<boolean> {
    isDisconnecting.value = true;
    errorMessage.value = null;
    try {
      await $fetch(`${apiBase}/api/v1/integrations/etsy`, {
        method: 'DELETE',
        headers: {
          Accept: 'application/json',
          ...getCsrfHeaders(),
        },
        credentials: 'include',
      });
      connectionStatus.value = {
        connected: false,
        connection_status: 'disconnected',
        granted_scopes: [],
        token_health: 'disconnected',
      };
      return true;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to disconnect Etsy shop.');
      return false;
    } finally {
      isDisconnecting.value = false;
    }
  }

  async function triggerCreateEtsyDraft(
    workflowId: string
  ): Promise<EtsyDraftDispatchResponse | null> {
    if (!workflowId) return null;
    isDispatching.value = true;
    errorMessage.value = null;

    try {
      const data = await $fetch<EtsyDraftDispatchResponse>(
        `${apiBase}/api/v1/workflows/${workflowId}/etsy/draft`,
        {
          method: 'POST',
          headers: {
            Accept: 'application/json',
            ...getCsrfHeaders(),
          },
          credentials: 'include',
        }
      );
      draftStatus.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to initiate Etsy draft creation.');
      return null;
    } finally {
      isDispatching.value = false;
    }
  }

  async function fetchDraftStatus(
    workflowId: string
  ): Promise<EtsyDraftDispatchResponse | null> {
    if (!workflowId) return null;
    try {
      const data = await $fetch<EtsyDraftDispatchResponse>(
        `${apiBase}/api/v1/workflows/${workflowId}/etsy/status`,
        {
          headers: { Accept: 'application/json' },
          credentials: 'include',
        }
      );
      draftStatus.value = data;
      return data;
    } catch (err: unknown) {
      errorMessage.value = getApiErrorMessage(err, 'Failed to poll Etsy draft status.');
      return null;
    }
  }

  return {
    connectionStatus,
    draftStatus,
    isLoading,
    isConnecting,
    isDisconnecting,
    isDispatching,
    errorMessage,
    fetchConnectionStatus,
    initiateOAuthConnect,
    disconnectShop,
    triggerCreateEtsyDraft,
    fetchDraftStatus,
  };
}
