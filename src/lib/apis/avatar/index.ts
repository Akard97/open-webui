import { WEBUI_API_BASE_URL } from '$lib/constants';

export const generateAvatar = async (
	token: string,
	photo: Blob,
	filename = 'photo.png'
): Promise<{ image: string; remaining: number }> => {
	const data = new FormData();
	data.append('photo', photo, filename);

	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/avatar/generate`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			authorization: `Bearer ${token}`
		},
		body: data
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail ?? err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getAvatarQuota = async (
	token: string
): Promise<{ remaining: number; limit: number }> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/avatar/quota`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail ?? err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
