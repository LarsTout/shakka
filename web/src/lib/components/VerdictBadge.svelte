<script lang="ts">
	import { verdictLabel } from '#lib/labels.js';
	import type { Verdict } from '#lib/types.js';

	let { verdict }: { verdict: Verdict } = $props();
</script>

<span class="verdict verdict-{verdict}" data-verdict={verdict}>{verdictLabel(verdict)}</span>
