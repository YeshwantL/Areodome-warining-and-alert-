async function handleLogin(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    try {
        const response = await fetch('/auth/token', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('token', data.access_token);
            localStorage.setItem('audio_enabled', 'true');
            window.location.href = '/dashboard';
        } else {
            document.getElementById('error-message').innerText = 'Invalid credentials';
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('error-message').innerText = 'An error occurred';
    }
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = '/login';
}

// Auth Interceptor for fetch
const originalFetch = window.fetch;
window.fetch = async function (url, options = {}) {
    const token = localStorage.getItem('token');
    if (token && !url.includes('/token')) {
        options.headers = options.headers || {};
        options.headers['Authorization'] = 'Bearer ' + token;
    }
    const response = await originalFetch(url, options);
    if (response.status === 401 && !url.includes('/token')) {
        // Token expired or invalid
        localStorage.removeItem('token');
        if (window.location.pathname !== '/login') {
            window.location.href = '/login';
        }
    }
    return response;
};
