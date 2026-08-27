import { WEBUI_API_BASE_URL } from '$lib/constants';

export const getModelAnalytics = async (
	token: string = '',
	startDate: number | null = null,
	endDate: number | null = null,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (startDate) searchParams.append('start_date', startDate.toString());
	if (endDate) searchParams.append('end_date', endDate.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/models?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUserAnalytics = async (
	token: string = '',
	startDate: number | null = null,
	endDate: number | null = null,
	limit: number = 50,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (startDate) searchParams.append('start_date', startDate.toString());
	if (endDate) searchParams.append('end_date', endDate.toString());
	if (limit) searchParams.append('limit', limit.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/users?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getMessages = async (
	token: string = '',
	modelId: string | null = null,
	userId: string | null = null,
	chatId: string | null = null,
	startDate: number | null = null,
	endDate: number | null = null,
	skip: number = 0,
	limit: number = 50
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (modelId) searchParams.append('model_id', modelId);
	if (userId) searchParams.append('user_id', userId);
	if (chatId) searchParams.append('chat_id', chatId);
	if (startDate) searchParams.append('start_date', startDate.toString());
	if (endDate) searchParams.append('end_date', endDate.toString());
	if (skip) searchParams.append('skip', skip.toString());
	if (limit) searchParams.append('limit', limit.toString());

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/messages?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getSummary = async (
	token: string = '',
	startDate: number | null = null,
	endDate: number | null = null,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (startDate) searchParams.append('start_date', startDate.toString());
	if (endDate) searchParams.append('end_date', endDate.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/summary?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getDailyStats = async (
	token: string = '',
	startDate: number | null = null,
	endDate: number | null = null,
	granularity: 'hourly' | 'daily' = 'daily',
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (startDate) searchParams.append('start_date', startDate.toString());
	if (endDate) searchParams.append('end_date', endDate.toString());
	searchParams.append('granularity', granularity);
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/daily?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getTokenUsage = async (
	token: string = '',
	startDate: number | null = null,
	endDate: number | null = null,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (startDate) searchParams.append('start_date', startDate.toString());
	if (endDate) searchParams.append('end_date', endDate.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/tokens?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getModelChats = async (
	token: string = '',
	modelId: string,
	startDate: number | null = null,
	endDate: number | null = null,
	skip: number = 0,
	limit: number = 50
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (startDate) searchParams.append('start_date', startDate.toString());
	if (endDate) searchParams.append('end_date', endDate.toString());
	if (skip) searchParams.append('skip', skip.toString());
	if (limit) searchParams.append('limit', limit.toString());

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/models/${encodeURIComponent(modelId)}/chats?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageOverview = async (
	token: string = '',
	days: number = 30,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/usage/overview?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageDaily = async (
	token: string = '',
	days: number = 30,
	tool: string | null = null,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	if (tool) searchParams.append('tool', tool);
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/usage/daily?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageEventCounts = async (
	token: string = '',
	days: number = 30,
	tool: string | null = null,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	if (tool) searchParams.append('tool', tool);
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/usage/events?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageUsers = async (
	token: string = '',
	days: number = 30,
	sort: string = 'events',
	page: number = 1,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	searchParams.append('sort', sort);
	searchParams.append('page', page.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/usage/users?${searchParams.toString()}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageUserActivity = async (
	token: string = '',
	userId: string,
	days: number = 30,
	page: number = 1,
	tool: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	searchParams.append('page', page.toString());
	if (tool) searchParams.append('tool', tool);

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/users/${encodeURIComponent(userId)}/activity?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsagePresence = async (token: string = '', groupId: string | null = null) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/presence?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageActive = async (
	token: string = '',
	days: number = 30,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/active?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageHeatmap = async (
	token: string = '',
	days: number = 30,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/heatmap?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageModels = async (
	token: string = '',
	days: number = 30,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/models?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageSessionsDaily = async (
	token: string = '',
	days: number = 30,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/sessions/daily?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageGroups = async (token: string = '', days: number = 30) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/groups?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageUserSummary = async (
	token: string = '',
	userId: string,
	days: number = 30
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/users/${userId}/summary?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getModelOverview = async (token: string = '', modelId: string, days: number = 30) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/models/${encodeURIComponent(modelId)}/overview?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
