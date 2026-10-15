import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({ deleteMyAccount: null as unknown, cleanUp: null as unknown }));
vi.mock('#lib/account.js', () => {
	const deleteMyAccount = vi.fn();
	const cleanUpAfterAccountDeletion = vi.fn(async () => {});
	h.deleteMyAccount = deleteMyAccount;
	h.cleanUp = cleanUpAfterAccountDeletion;
	return { deleteMyAccount, cleanUpAfterAccountDeletion };
});

import DeleteAccount from '../src/lib/components/DeleteAccount.svelte';

const del = () => h.deleteMyAccount as ReturnType<typeof vi.fn>;
const cleanUp = () => h.cleanUp as ReturnType<typeof vi.fn>;

beforeEach(() => {
	vi.clearAllMocks();
	del().mockResolvedValue({ ok: true });
});

const open = async (ondeleted = vi.fn()) => {
	render(DeleteAccount, { ondeleted });
	const user = userEvent.setup();
	await user.click(screen.getByRole('button', { name: 'Account verwijderen…' }));
	return { user, ondeleted };
};

describe('DeleteAccount', () => {
	it('opens the confirmation and focuses "Weet je het zeker?"', async () => {
		await open();
		expect(screen.getByText('Weet je het zeker?').closest('p')).toHaveFocus();
	});
	it('cancel closes it and returns focus to the button', async () => {
		const { user } = await open();
		await user.click(screen.getByRole('button', { name: 'Annuleren' }));
		const ask = screen.getByRole('button', { name: 'Account verwijderen…' });
		await waitFor(() => expect(ask).toHaveFocus());
		expect(screen.queryByText('Weet je het zeker?')).not.toBeInTheDocument();
	});
	it('confirming deletes once, then calls ondeleted and the cleanup', async () => {
		const { user, ondeleted } = await open();
		await user.click(screen.getByRole('button', { name: 'Ja, verwijder mijn account' }));
		await waitFor(() => expect(cleanUp()).toHaveBeenCalledTimes(1));
		expect(del()).toHaveBeenCalledTimes(1);
		expect(ondeleted).toHaveBeenCalledTimes(1);
	});
	it('disables the buttons while busy and ignores a second click', async () => {
		let release!: (v: { ok: true }) => void;
		del().mockReturnValue(new Promise((r) => (release = r)));
		const { user } = await open();
		await user.click(screen.getByRole('button', { name: 'Ja, verwijder mijn account' }));
		const busyBtn = screen.getByRole('button', { name: 'Bezig met verwijderen…' });
		expect(busyBtn).toBeDisabled();
		expect(screen.getByRole('button', { name: 'Annuleren' })).toBeDisabled();
		await user.click(busyBtn);
		expect(del()).toHaveBeenCalledTimes(1);
		release({ ok: true });
		await waitFor(() => expect(cleanUp()).toHaveBeenCalled());
	});
	it('shows the error, keeps the confirmation open and does not call ondeleted', async () => {
		del().mockResolvedValue({ ok: false, error: 'Nope, probeer later.' });
		const { user, ondeleted } = await open();
		await user.click(screen.getByRole('button', { name: 'Ja, verwijder mijn account' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('Nope, probeer later.');
		expect(ondeleted).not.toHaveBeenCalled();
		expect(cleanUp()).not.toHaveBeenCalled();
		expect(screen.getByText('Weet je het zeker?')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Ja, verwijder mijn account' })).toBeEnabled();
	});
});
