// SCANNER
var html5QrcodeScanner = new Html5QrcodeScanner(
    "reader", { fps: 10, qrbox: 250 }
);
html5QrcodeScanner.render(onScanSuccess);

// AUDIO
const audio_success = new Audio('/static/audio/success.mp3');
const audio_failed = new Audio('/static/audio/failed.mp3');


function parseTicketQr(str) {
    const text = (str || '').trim();
    if (!text) {
        throw new Error("QR code not recognised!");
    }

    if (text.includes('participant_id:')) {
        const match = text.match(/participant_id:(\d+)/);
        if (!match) {
            throw new Error("QR code not recognised!");
        }

        const keyword = "seed:";
        const startIndex = text.indexOf(keyword);
        if (startIndex === -1) {
            throw new Error("QR code not recognised!");
        }

        const seed = text.substring(startIndex + keyword.length).trim();
        if (!seed) {
            throw new Error("QR code not recognised!");
        }

        return {
            participantId: parseInt(match[1], 10),
            seed: seed,
        };
    }

    if (text.length < 11) {
        throw new Error("QR code not recognised!");
    }

    const seed = text.slice(-10);
    const idPart = text.slice(0, -10);
    if (!/^\d+$/.test(idPart) || !/^[A-Za-z0-9]+$/.test(seed)) {
        throw new Error("QR code not recognised!");
    }

    return {
        participantId: parseInt(idPart, 10),
        seed: seed,
    };
}

let isCooldown = false;
const cooldownDuration = 4000;

function onScanSuccess(decodedText, decodedResult) {
    if (isCooldown) {
        console.log("Cooldown active. Scan ignored.");
        return;
    }

    isCooldown = true;
    setTimeout(() => {
        isCooldown = false;
        document.getElementById('status-text').innerText = "Ticket Scanner";
        document.getElementById('status-bar').classList.replace('bg-success', 'bg-primary');
        document.getElementById('status-bar').classList.replace('bg-danger', 'bg-primary');
    }, cooldownDuration);

    var id = -1;
    var seed = '';

    try {
        const parsed = parseTicketQr(decodedText);
        id = parsed.participantId;
        seed = parsed.seed;
    } catch (error) {
        return setStatusToFailed(error.message);
    }

    // set the button link to the deelnemer link
    document.getElementById('deelnemer-btn').href = `${getBaseUrl()}admin/pokemon/participant/${id}/change/`;

    // set attendance
    fetch('/pokemon/set-attendance/', {
        method: 'POST',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': '{{ csrf_token }}'
        },
        body: JSON.stringify({ 'participant_id': id, 'seed': seed })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('response').value = data.message;
        
        return data.success ? setStatusToSuccess(data.message) : setStatusToFailed(data.message);
    })
    .catch((error) => {
        return setStatusToFailed(error.message);
    });
}

function setStatusToSuccess(message) {
    document.getElementById('status-text').innerText = "Deelnemer Geregistreerd!";
    document.getElementById('status-bar').classList.replace('bg-primary', 'bg-success');
    document.getElementById('status-bar').classList.replace('bg-danger', 'bg-success');

    document.getElementById('response').innerText = message;

    //play beep
    audio_success.play();
}

function setStatusToFailed(message) {
    document.getElementById('status-text').innerText = "Er is een probleem!";
    document.getElementById('status-bar').classList.replace('bg-primary', 'bg-danger');
    document.getElementById('status-bar').classList.replace('bg-success', 'bg-danger');

    document.getElementById('response').innerText = message;

    //play error
    audio_failed.play();
}


function getBaseUrl() {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const port = window.location.port;

    let baseUrl = `${protocol}//${hostname}`;
    if (port) {
        baseUrl += `:${port}`;
    }

    return baseUrl + '/';
}
