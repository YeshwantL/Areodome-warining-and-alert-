async function handleLogin(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    
    try {
        const response = await fetch('/token', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('token', data.access_token);
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
window.fetch = async function(url, options = {}) {
    const token = localStorage.getItem('token');
    if (token && !url.includes('/token')) {
        options.headers = options.headers || {};
        options.headers['Authorization'] = 'Bearer ' + token;
    }
    return originalFetch(url, options);
};
