import { WEBUI_API_BASE_URL } from '$lib/constants';

const jsonHeaders = (token: string) => ({
	Accept: 'application/json',
	'Content-Type': 'application/json',
	authorization: `Bearer ${token}`
});

const handle = async (res: Response) => {
	if (!res.ok) throw await res.json();
	return res.json();
};

export const getSites = async (token: string = '', all: boolean = false) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/${all ? '?all=true' : ''}`, {
		method: 'GET',
		headers: jsonHeaders(token)
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};

export const getSiteById = async (token: string = '', id: string) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/${encodeURIComponent(id)}`, {
		method: 'GET',
		headers: jsonHeaders(token)
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};

export const createSite = async (token: string = '', formData: FormData) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/`, {
		method: 'POST',
		headers: { Accept: 'application/json', authorization: `Bearer ${token}` },
		body: formData
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};

export const updateSite = async (token: string = '', id: string, formData: FormData) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/${encodeURIComponent(id)}/update`, {
		method: 'POST',
		headers: { Accept: 'application/json', authorization: `Bearer ${token}` },
		body: formData
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};

export const updateSiteAccess = async (
	token: string = '',
	id: string,
	body: { public: boolean; access_grants: any[] }
) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/${encodeURIComponent(id)}/access`, {
		method: 'POST',
		headers: jsonHeaders(token),
		body: JSON.stringify(body)
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};

export const deleteSite = async (token: string = '', id: string) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/${encodeURIComponent(id)}`, {
		method: 'DELETE',
		headers: jsonHeaders(token)
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};

export const getSiteAnalytics = async (token: string = '', id: string, days: number = 30) => {
	let error = null;
	const res = await fetch(
		`${WEBUI_API_BASE_URL}/sites/${encodeURIComponent(id)}/analytics?days=${days}`,
		{
			method: 'GET',
			headers: jsonHeaders(token)
		}
	)
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};
