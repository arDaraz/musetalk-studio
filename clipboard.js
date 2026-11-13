() => {
    function mediaKind(file) {
        if (file.type.startsWith("image/") || /\.(png|jpe?g|webp|gif|bmp|tiff?|avif|heic)$/i.test(file.name)) return "image";
        if (file.type.startsWith("audio/") || /\.(wav|mp3|m4a|aac|flac|ogg|opus|aiff?|webm)$/i.test(file.name)) return "audio";
        return null;
    }

    function pasteTarget(element) {
        const zone = element.closest("[data-clipboard-kind]");
        if (zone) return zone.dataset.clipboardKind;
        if (element.closest("#photo-input")) return "image";
        if (element.closest("#audio-input")) return "audio";
        if (element.closest("#reference-input")) return "reference";
        return null;
    }

    async function uploadFile(component, file) {
        let input = component.querySelector('input[type="file"]');
        if (!input) {
            const clear = component.querySelector('button[aria-label="Clear"]');
            if (!clear) return false;
            clear.click();
            await new Promise(requestAnimationFrame);
            input = component.querySelector('input[type="file"]');
        }
        if (!input) return false;
        const transfer = new DataTransfer();
        transfer.items.add(file);
        input.files = transfer.files;
        input.dispatchEvent(new Event("change", {bubbles: true}));
        return true;
    }

    async function pasteMedia(event) {
        const kind = pasteTarget(event.target);
        if (!kind || !event.clipboardData) return;
        const status = document.querySelector(`[data-clipboard-kind="${kind}"] [role="status"]`);
        const files = Array.from(event.clipboardData.files).filter(file => mediaKind(file) === (kind === "reference" ? "audio" : kind));
        event.preventDefault();
        event.stopPropagation();
        if (files.length !== 1) {
            status.textContent = `Copy one ${kind === "image" ? "photo" : "audio file"}, then paste here. Text and file paths cannot be uploaded.`;
            return;
        }
        const component = document.querySelector(({image: "#photo-input", audio: "#audio-input", reference: "#reference-input"})[kind]);
        const uploaded = await uploadFile(component, files[0]);
        status.textContent = uploaded
            ? "Pasted. Check the preview above. You can paste again to replace it."
            : "The upload field is not ready. Please paste again.";
    }

    function focusOnHover(event) {
        const target = event.target.closest('#photo-input, #audio-input, #reference-input, [data-clipboard-kind]');
        if (!target || event.pointerType === "touch") return;
        if (target.contains(event.relatedTarget) || target.contains(document.activeElement)) return;
        if (!target.hasAttribute("tabindex")) target.tabIndex = -1;
        target.focus({preventScroll: true});
    }

    document.addEventListener("pointerover", focusOnHover);
    document.addEventListener("paste", pasteMedia, true);
}
