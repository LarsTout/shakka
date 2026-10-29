<script lang="ts">
	import { verdictLabel } from '#lib/labels.js';
	import type { Verdict } from '#lib/types.js';

	let { verdict, size = 'sm' }: { verdict: Verdict; size?: 'sm' | 'lg' } = $props();
</script>

<span class={['verdict', `verdict-${verdict}`, size === 'lg' && 'verdict-lg']} data-verdict={verdict}>{verdictLabel(verdict)}</span>
