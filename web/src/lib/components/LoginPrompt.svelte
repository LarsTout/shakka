<script lang="ts">
	let { reason }: { reason: string } = $props();
</script>

<div class="login-prompt">
	<p>Log in om {reason}.</p>
	<p><a href="/login">Inloggen</a></p>
</div>
