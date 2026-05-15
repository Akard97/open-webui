<!--
  Policy Review embed — hosts the standalone Policy Review FastAPI
  service (port 8100) in an iframe so it renders inside the Hub
  chrome (AppSidebar stays visible).

  The PRP frontend trips its own embed mode (hides GlobalRail and
  HubSidebar switch-tool button) via the `?embed=1` query AND iframe
  detection — see policy_review/static/interactive-prp.jsx.

  Hard-coded URL today (trust-localhost posture). When the Hub moves
  off localhost, swap this for an env-driven URL and pass a bearer
  token via the hash (`#token=…`) — the PRP frontend already has the
  seam to read it.
-->
<svelte:head>
	<title>Policy Review · Osool</title>
</svelte:head>

<iframe
	src="http://localhost:8100/ui/?embed=1"
	title="Policy Review"
	class="w-full h-full border-0"
	allow="clipboard-read; clipboard-write"
></iframe>
