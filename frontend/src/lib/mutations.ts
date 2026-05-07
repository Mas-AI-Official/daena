/**
 * Shared mutation helpers with consistent toast behavior.
 *
 * Why this exists: every page that deleted something used to roll its
 * own ``try { api.delete } catch { toast.error(...) }`` block, and
 * the behavior drifted -- FilesPage toasted per-delete and again on
 * batch completion even when half the items failed; TasksPage
 * silently swallowed errors and showed no toast at all;
 * ProjectsPage did neither success nor failure feedback. The user
 * called this out directly: "all the error handlers for delete or
 * something like that is different." This module is the one place
 * where "what should a delete look like" is answered.
 *
 * Usage:
 *     await deleteWithToast('/files/abc', { entity: 'File' })
 *     await batchDeleteWithToast(ids, (id) => \`/files/\${id}\`,
 *                                { entity: 'file' })
 */
import { api } from '@/lib/api'
import { confirmDialog } from '@/stores/confirmStore'
import { toast } from '@/stores/toastStore'

export interface DeleteOptions {
  /** Entity name for the toast, e.g. 'File', 'Task'. */
  entity?: string
  /** Override the success toast. */
  successMessage?: string
  /** Override the failure toast. If omitted, uses the backend detail or a default. */
  failureMessage?: string
  /** Suppress the toast entirely (used by batch helpers). */
  silent?: boolean
  /**
   * When provided, a themed confirmation dialog is shown before the
   * delete fires. The string is the dialog body. Returns false (and
   * skips the network call) if the user cancels.
   */
  confirmMessage?: string
}

/**
 * DELETE a single resource with standard toast feedback.
 *
 * Returns ``true`` on success, ``false`` on failure. The caller can
 * still branch on the boolean if they want to update local state.
 */
export async function deleteWithToast(
  path: string,
  opts: DeleteOptions = {},
): Promise<boolean> {
  const entity = opts.entity ?? 'Item'
  if (opts.confirmMessage) {
    const ok = await confirmDialog({
      title: `Delete ${entity.toLowerCase()}?`,
      message: opts.confirmMessage,
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) return false
  }
  try {
    await api.delete(path)
    if (!opts.silent) {
      toast.success(opts.successMessage ?? `${entity} deleted`)
    }
    return true
  } catch (err: unknown) {
    if (opts.silent) return false
    const detail =
      (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail ?? undefined
    toast.error(
      opts.failureMessage ??
        (detail ? `Delete failed: ${detail}` : `Failed to delete ${entity.toLowerCase()}`),
    )
    return false
  }
}

export interface BatchDeleteOptions {
  /** Lowercase singular entity, e.g. 'file', 'task', 'project'. */
  entity: string
  /** Optional confirmation message. Skipped when ``confirm`` is false. */
  confirmMessage?: string
  /** Require confirm() before running. Default: true. */
  confirm?: boolean
}

export interface BatchDeleteResult {
  total: number
  succeeded: number
  failed: number
}

/**
 * Delete many resources, with one summary toast at the end.
 *
 * Failures don't stop the batch. After the batch:
 *   - All succeeded   → toast.success("N files deleted")
 *   - Some failed     → toast.warning("N deleted, M failed")
 *   - All failed      → toast.error("Failed to delete N files")
 */
export async function batchDeleteWithToast<TId>(
  ids: Iterable<TId>,
  pathFn: (id: TId) => string,
  opts: BatchDeleteOptions,
): Promise<BatchDeleteResult> {
  const idArray = Array.from(ids)
  const total = idArray.length
  if (total === 0) {
    return { total: 0, succeeded: 0, failed: 0 }
  }

  if (opts.confirm !== false) {
    // Themed modal instead of native confirm() so the dialog matches
    // the rest of the UI (dark slate + accent) rather than OS chrome.
    const plural = opts.entity + (total > 1 ? 's' : '')
    const ok = await confirmDialog({
      title: `Delete ${total} ${plural}?`,
      message: opts.confirmMessage ?? 'This cannot be undone.',
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) {
      return { total, succeeded: 0, failed: 0 }
    }
  }

  let succeeded = 0
  let failed = 0
  // Serial to avoid hammering the backend; these are admin operations
  // where predictable order > parallel speed.
  for (const id of idArray) {
    const ok = await deleteWithToast(pathFn(id), { silent: true })
    if (ok) succeeded += 1
    else failed += 1
  }

  const plural = opts.entity + (total > 1 ? 's' : '')
  if (failed === 0) {
    toast.success(`${succeeded} ${plural} deleted`)
  } else if (succeeded === 0) {
    toast.error(`Failed to delete ${failed} ${plural}`)
  } else {
    toast.warning(`${succeeded} ${plural} deleted, ${failed} failed`)
  }

  return { total, succeeded, failed }
}
