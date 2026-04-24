// Unsaved-changes tracking.
//
// Model: the page is "dirty" once any form input fires input/change, and
// cleared by a successful HTMX response (form save, add, remove, etc).
// An active sidebar link shows a * marker when dirty; navigating away
// with pending changes shows the browser's native confirmation.
(function () {
    'use strict';

    let dirty = false;

    function activeLink() {
        return document.querySelector('.sidebar a.active');
    }

    function markDirty() {
        if (dirty) return;
        dirty = true;
        const link = activeLink();
        if (link) link.classList.add('dirty');
    }

    function clearDirty() {
        if (!dirty) return;
        dirty = false;
        const link = activeLink();
        if (link) link.classList.remove('dirty');
    }

    document.addEventListener('input', function (e) {
        if (e.target.closest('form')) markDirty();
    });
    document.addEventListener('change', function (e) {
        if (e.target.closest('form')) markDirty();
    });

    document.addEventListener('htmx:afterRequest', function (e) {
        if (e.detail.successful) clearDirty();
    });

    window.addEventListener('beforeunload', function (e) {
        if (dirty) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    // Auto-fade the "Saved" indicator 2 seconds after each swap.
    document.addEventListener('htmx:afterSwap', function () {
        document.querySelectorAll('.saved-indicator').forEach(function (el) {
            setTimeout(function () {
                el.remove();
            }, 2000);
        });
    });
})();
