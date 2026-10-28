<script lang="ts">
	import type { Timeline } from '#lib/timeline.js';

	let { timeline, size = 'md' }: { timeline: Timeline; size?: 'sm' | 'md' | 'lg' } = $props();
</script>

<div class="timeline timeline-{size}" aria-hidden="true">
	<div class="timeline-track">
		{#if size === 'lg'}{#each timeline.markers as m (m.kind + m.pos)}
				<span
					class="timeline-marker timeline-marker-{m.kind}"
					class:timeline-marker-row2={m.row === 1}
					class:timeline-marker-end={m.pos > 0.8}
					style:left="{m.pos * 100}%">{m.label}</span
				>
			{/each}{/if}
		<div class="timeline-bar">
			{#each timeline.slots as k, i (i)}<span class="slot slot-{k}"></span>{/each}
		</div>
		{#if timeline.window}<span
				class="timeline-window"
				style:left="{timeline.window.from * 100}%"
				style:width="{(timeline.window.to - timeline.window.from) * 100}%"
			></span>{/if}
	</div>
	{#if size !== 'sm'}<div class="timeline-ticks">
			{#each timeline.ticks as t (t.pos)}<span
					class="timeline-tick"
					class:timeline-tick-start={t.pos === 0}
					class:timeline-tick-end={t.pos === 1}
					style:left="{t.pos * 100}%">{t.label}</span
				>{/each}
		</div>{/if}
</div>

<style>
	.timeline {
		forced-color-adjust: none;
		margin-block: var(--space-2);
	}
	.timeline-track {
		position: relative;
	}
	.timeline-lg .timeline-track {
		padding-top: 2.5rem;
	}
	.timeline-bar {
		display: flex;
		gap: 2px;
		height: 0.5rem;
	}
	.timeline-sm .timeline-bar {
		gap: 1px;
		height: 0.25rem;
	}
	.timeline-lg .timeline-bar {
		height: 1.75rem;
	}
	.slot {
		flex: 1 1 0;
		min-width: 0;
	}
	.slot:first-child {
		border-top-left-radius: 2px;
		border-bottom-left-radius: 2px;
	}
	.slot:last-child {
		border-top-right-radius: 2px;
		border-bottom-right-radius: 2px;
	}
	.slot-go {
		background: var(--color-go);
	}
	.slot-marginal {
		background: var(--color-marginal);
	}
	.slot-no_go {
		background: var(--color-no-go);
	}
	.slot-none {
		background: repeating-linear-gradient(135deg, var(--color-none) 0 1px, transparent 1px 4px);
	}
	.slot-outside,
	.slot-free {
		background: var(--color-border);
	}
	.slot-quiet {
		background: var(--color-muted);
	}
	.timeline-window {
		position: absolute;
		bottom: -0.3rem;
		height: calc(1.75rem + 0.6rem);
		box-sizing: border-box;
		border: 1.5px solid var(--color-text);
		border-radius: 3px;
		pointer-events: none;
	}
	.timeline-marker {
		position: absolute;
		top: 1.25rem;
		bottom: 0;
		padding-top: 0;
		font-size: var(--font-size-xs);
		line-height: 1.1;
		white-space: nowrap;
		color: var(--color-text);
		border-left: 1px dotted var(--color-muted);
		padding-left: 0.2rem;
	}
	.timeline-marker-now {
		border-left: 1.5px solid var(--color-text);
	}
	.timeline-marker-row2 {
		top: 0;
	}
	.timeline-marker-end {
		transform: translateX(-100%);
		border-left: 0;
		border-right: 1px dotted var(--color-muted);
		padding-left: 0;
		padding-right: 0.2rem;
	}
	.timeline-marker-end.timeline-marker-now {
		border-right: 1.5px solid var(--color-text);
	}
	.timeline-ticks {
		position: relative;
		height: 1rem;
		margin-top: var(--space-1);
		font-size: var(--font-size-xs);
		color: var(--color-muted);
	}
	.timeline-tick {
		position: absolute;
		transform: translateX(-50%);
	}
	.timeline-tick-start {
		transform: none;
	}
	.timeline-tick-end {
		transform: translateX(-100%);
	}
</style>
