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

    const camera = {stream: null, countdown: null, request: 0};
    const cameraErrors = {
        SecurityError: ["This page cannot use the camera", "Open the page at http://127.0.0.1 or localhost, then click Try again."],
        NotAllowedError: ["The browser blocked the camera", "Click the camera icon in the address bar and choose Allow. Then click Try again."],
        NotFoundError: ["No camera found", "Connect a camera, then click Try again."],
        NotReadableError: ["The camera is in use", "Close the other app that uses the camera, then click Try again."],
    };

    // Gradio copies each page rule inside .contain with higher specificity. So the camera state attribute must be on an element inside .contain.
    function cameraRoot() {
        return document.querySelector(".studio-main");
    }

    function cameraPart(selector) {
        return document.querySelector(`.camera-panel ${selector}`);
    }

    function showCamera(state) {
        cameraRoot().dataset.camera = state;
    }

    function stopCamera() {
        camera.request += 1;
        clearInterval(camera.countdown);
        camera.stream?.getTracks().forEach(track => track.stop());
        camera.stream = null;
    }

    function closeCamera() {
        stopCamera();
        delete cameraRoot().dataset.camera;
    }

    function showCameraError(error) {
        const [title, text] = cameraErrors[error.name] || ["The camera did not start", error.message];
        cameraPart(".camera-error strong").textContent = title;
        cameraPart(".camera-error span").textContent = text;
        showCamera("error");
    }

    async function listCameras() {
        const select = cameraPart("select");
        const current = camera.stream.getVideoTracks()[0].getSettings().deviceId;
        const devices = (await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === "videoinput");
        select.replaceChildren(...devices.map((device, index) =>
            new Option(device.label || `Camera ${index + 1}`, device.deviceId, false, device.deviceId === current)));
    }

    async function openCamera() {
        stopCamera();
        if (!navigator.mediaDevices) return showCameraError({name: "SecurityError"});
        showCamera("live");
        const request = camera.request;
        const deviceId = cameraPart("select").value;
        const video = {width: {ideal: 1920}, height: {ideal: 1080}, ...(deviceId && {deviceId: {exact: deviceId}})};
        try {
            const stream = await navigator.mediaDevices.getUserMedia({video, audio: false});
            if (request !== camera.request) {
                stream.getTracks().forEach(track => track.stop());
                return;
            }
            camera.stream = stream;
            cameraPart("video").srcObject = stream;
            await listCameras();
        } catch (error) {
            if (request === camera.request) showCameraError(error);
        }
    }

    function capture() {
        const video = cameraPart("video");
        const shot = Object.assign(cameraPart(".camera-shot"), {width: video.videoWidth, height: video.videoHeight});
        shot.getContext("2d").drawImage(video, 0, 0);
        stopCamera();
        cameraPart(".camera-size").textContent = `${shot.width} × ${shot.height} pixels.`;
        showCamera("review");
    }

    function shoot() {
        if (cameraRoot().dataset.camera !== "live" || !cameraPart("video").videoWidth) return;
        if (!cameraPart("input[type=checkbox]").checked) return capture();
        const counter = cameraPart(".countdown");
        let count = 3;
        counter.textContent = count;
        showCamera("countdown");
        camera.countdown = setInterval(() => {
            count -= 1;
            if (count > 0) {
                counter.textContent = count;
                return;
            }
            clearInterval(camera.countdown);
            capture();
        }, 1000);
    }

    async function usePhoto() {
        const blob = await new Promise(resolve => cameraPart(".camera-shot").toBlob(resolve, "image/png"));
        const photo = new File([blob], "camera-photo.png", {type: "image/png"});
        if (await uploadFile(document.querySelector("#photo-input"), photo)) {
            closeCamera();
        } else {
            cameraPart(".camera-size").textContent = "The photo box is not ready. Click Use this photo again.";
        }
    }

    function chooseFile() {
        const picker = Object.assign(document.createElement("input"), {type: "file", accept: "image/*"});
        picker.addEventListener("change", () => {
            if (picker.files.length) uploadFile(document.querySelector("#photo-input"), picker.files[0]);
        });
        picker.click();
    }

    const photoActions = {choose: chooseFile, camera: openCamera, cancel: closeCamera, shoot, use: usePhoto};

    document.addEventListener("click", event => {
        const button = event.target.closest("[data-photo-action]");
        if (button) photoActions[button.dataset.photoAction]();
    });
    document.addEventListener("change", event => {
        if (event.target.matches(".camera-panel select")) openCamera();
    });
    document.addEventListener("pointerover", focusOnHover);
    document.addEventListener("paste", pasteMedia, true);
}
