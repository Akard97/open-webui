import { WEBUI_API_BASE_URL } from '$lib/constants';
import type { ChecklistVersion, Review, LibraryPolicy } from './types';

const BASE = `${WEBUI_API_BASE_URL}/policy`;

async function request<T>(token: string, path: string, method = 'GET', body?: unknown): Promise<T> {
	let error: unknown = null;
	const res = await fetch(`${BASE}${path}`, {
		method,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		...(body !== undefined ? { body: JSON.stringify(body) } : {})
	})
		.then(async (r) => {
			if (!r.ok) throw await r.json();
			return r.json();
		})
		.catch((err) => {
			error = err?.detail ?? err;
			console.error(error);
			return null;
		});
	if (error) throw error;
	return res as T;
}

// ── Checklist ──
export const getActiveChecklist = (token: string) =>
	request<ChecklistVersion>(token, '/checklist/active');
export const getChecklistVersions = (token: string) =>
	request<ChecklistVersion[]>(token, '/checklist/versions');
export const getChecklistDraft = (token: string) =>
	request<ChecklistVersion | null>(token, '/checklist/draft');
export const startChecklistDraft = (token: string) =>
	request<ChecklistVersion>(token, '/checklist/draft', 'POST');
export const saveChecklistDraft = (token: string, data: unknown) =>
	request<ChecklistVersion>(token, '/checklist/draft', 'PUT', { data });
export const publishChecklistDraft = (token: string) =>
	request<ChecklistVersion>(token, '/checklist/draft/publish', 'POST');
export const discardChecklistDraft = (token: string) =>
	request<{ success: boolean }>(token, '/checklist/draft', 'DELETE');
export const activateVersionApi = (token: string, id: string) =>
	request<ChecklistVersion>(token, `/checklist/versions/${id}/activate`, 'POST');

// ── Reviews ──
export const createReviewApi = (token: string, policy_meta: unknown, strengths: string[] = []) =>
	request<Review>(token, '/reviews', 'POST', { policy_meta, strengths });
export const getMyReviews = (token: string) => request<Review[]>(token, '/reviews/mine');
export const getApprovalQueue = (token: string) => request<Review[]>(token, '/reviews/queue');
export const getReviewApi = (token: string, id: string) => request<Review>(token, `/reviews/${id}`);
export const updateResultsApi = (token: string, id: string, results: unknown) =>
	request<Review>(token, `/reviews/${id}/results`, 'PATCH', { results });
export const submitReviewApi = (token: string, id: string, note = '') =>
	request<Review>(token, `/reviews/${id}/submit`, 'POST', { note });
export const approveReviewApi = (token: string, id: string, note: string) =>
	request<Review>(token, `/reviews/${id}/approve`, 'POST', { note });
export const rejectReviewApi = (token: string, id: string, note: string) =>
	request<Review>(token, `/reviews/${id}/reject`, 'POST', { note });
export const deleteReviewApi = (token: string, id: string) =>
	request<{ success: boolean }>(token, `/reviews/${id}`, 'DELETE');

// ── Library ──
export const getLibrary = (token: string) =>
	request<Array<{ code: string; data: LibraryPolicy }>>(token, '/library');
export const deleteLibraryApi = (token: string, code: string) =>
	request<{ success: boolean }>(token, `/library/${encodeURIComponent(code)}`, 'DELETE');
