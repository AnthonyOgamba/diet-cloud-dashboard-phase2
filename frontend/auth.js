"use strict";

const AUTH_API_BASE =
    "https://anthony-diet-dashboard-99241.azurewebsites.net/api";

const TOKEN_KEY = "dietDashboardAuthToken";

let currentAuthType = null;


/* =========================================================
   ELEMENTS
========================================================= */

function getAuthElements() {
    return {
        authSection: document.getElementById("auth-section"),
        dashboard: document.getElementById("main-content"),
        userArea: document.getElementById("user-area"),
        currentUserName: document.getElementById("current-user-name"),

        loginForm: document.getElementById("login-form"),
        registerForm: document.getElementById("register-form"),

        showLoginButton: document.getElementById("show-login-button"),
        showRegisterButton: document.getElementById("show-register-button"),

        loginEmail: document.getElementById("login-email"),
        loginPassword: document.getElementById("login-password"),

        registerName: document.getElementById("register-name"),
        registerEmail: document.getElementById("register-email"),
        registerPassword: document.getElementById("register-password"),

        logoutButton: document.getElementById("logout-button"),
        authMessage: document.getElementById("auth-message")
    };
}


/* =========================================================
   AUTH SCREEN
========================================================= */

function showAuthScreen() {
    const elements = getAuthElements();

    elements.authSection.hidden = false;
    elements.dashboard.hidden = true;
    elements.userArea.hidden = true;

    currentAuthType = null;
}


function showDashboard(user, authType) {
    const elements = getAuthElements();

    currentAuthType = authType;

    elements.authSection.hidden = true;
    elements.dashboard.hidden = false;
    elements.userArea.hidden = false;

    elements.currentUserName.textContent =
        user?.name ||
        user?.userDetails ||
        user?.email ||
        "User";

    /*
     * Tell app.js that authentication succeeded.
     * app.js will load the dashboard only after this event.
     */
    window.dispatchEvent(
        new CustomEvent(
            "dashboard-authenticated",
            {
                detail: {
                    user,
                    authType
                }
            }
        )
    );
}


/* =========================================================
   MESSAGE
========================================================= */

function showAuthMessage(message, type = "") {
    const element = document.getElementById("auth-message");

    if (!element) return;

    element.textContent = message;

    element.className =
        `auth-message${type ? ` ${type}` : ""}`;
}


/* =========================================================
   LOGIN / REGISTER TABS
========================================================= */

function showLoginForm() {
    const elements = getAuthElements();

    elements.loginForm.hidden = false;
    elements.registerForm.hidden = true;

    elements.showLoginButton.classList.add("active");
    elements.showRegisterButton.classList.remove("active");

    showAuthMessage("");
}


function showRegisterForm() {
    const elements = getAuthElements();

    elements.loginForm.hidden = true;
    elements.registerForm.hidden = false;

    elements.showRegisterButton.classList.add("active");
    elements.showLoginButton.classList.remove("active");

    showAuthMessage("");
}


/* =========================================================
   LOCAL EMAIL/PASSWORD LOGIN
========================================================= */

async function loginWithEmail(email, password) {
    const response = await fetch(
        `${AUTH_API_BASE}/auth/login`,
        {
            method: "POST",

            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },

            body: JSON.stringify({
                email,
                password
            })
        }
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data?.error ||
            `Login failed with HTTP ${response.status}.`
        );
    }

    if (!data.token || !data.user) {
        throw new Error(
            "The login response did not contain the expected user and token."
        );
    }

    sessionStorage.setItem(
        TOKEN_KEY,
        data.token
    );

    return data.user;
}


/* =========================================================
   REGISTER
========================================================= */

async function registerUser(name, email, password) {
    const response = await fetch(
        `${AUTH_API_BASE}/auth/register`,
        {
            method: "POST",

            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },

            body: JSON.stringify({
                name,
                email,
                password
            })
        }
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data?.error ||
            `Registration failed with HTTP ${response.status}.`
        );
    }

    return data;
}


/* =========================================================
   VALIDATE LOCAL JWT
========================================================= */

async function getLocalAuthenticatedUser() {
    const token = sessionStorage.getItem(
        TOKEN_KEY
    );

    if (!token) {
        return null;
    }

    try {
        const response = await fetch(
            `${AUTH_API_BASE}/auth/me`,
            {
                headers: {
                    "Accept": "application/json",
                    "Authorization": `Bearer ${token}`
                }
            }
        );

        if (!response.ok) {
            sessionStorage.removeItem(
                TOKEN_KEY
            );

            return null;
        }

        const data = await response.json();

        return data.user || null;

    } catch (error) {
        console.error(
            "Unable to validate local authentication:",
            error
        );

        return null;
    }
}


/* =========================================================
   AZURE STATIC WEB APPS / GITHUB OAUTH
========================================================= */

async function getGitHubAuthenticatedUser() {
    try {
        const response = await fetch(
            "/.auth/me",
            {
                headers: {
                    "Accept": "application/json"
                }
            }
        );

        if (!response.ok) {
            return null;
        }

        const data = await response.json();

        const principal = data?.clientPrincipal;

        if (!principal) {
            return null;
        }

        if (
            principal.identityProvider !== "github"
        ) {
            return null;
        }

        if (
            !Array.isArray(principal.userRoles) ||
            !principal.userRoles.includes("authenticated")
        ) {
            return null;
        }

        return {
            id: principal.userId,
            name: principal.userDetails,
            userDetails: principal.userDetails,
            provider: "github"
        };

    } catch (error) {
        console.error(
            "Unable to read GitHub authentication:",
            error
        );

        return null;
    }
}


/* =========================================================
   INITIAL AUTH CHECK
========================================================= */

async function initializeAuthentication() {
    showAuthMessage(
        "Checking authentication…"
    );

    /*
     * GitHub OAuth is checked first because Azure Static
     * Web Apps manages that session independently.
     */
    const githubUser =
        await getGitHubAuthenticatedUser();

    if (githubUser) {
        showDashboard(
            githubUser,
            "github"
        );

        return;
    }

    /*
     * If no GitHub session exists, check our custom JWT.
     */
    const localUser =
        await getLocalAuthenticatedUser();

    if (localUser) {
        showDashboard(
            localUser,
            "local"
        );

        return;
    }

    showAuthScreen();

    showAuthMessage(
        "Sign in to access the dashboard."
    );
}


/* =========================================================
   LOCAL LOGIN SUBMISSION
========================================================= */

async function handleLogin(event) {
    event.preventDefault();

    const elements = getAuthElements();

    const email =
        elements.loginEmail.value
            .trim()
            .toLowerCase();

    const password =
        elements.loginPassword.value;

    showAuthMessage(
        "Signing in…"
    );

    try {
        const user =
            await loginWithEmail(
                email,
                password
            );

        elements.loginForm.reset();

        showDashboard(
            user,
            "local"
        );

    } catch (error) {
        console.error(
            "Login error:",
            error
        );

        showAuthMessage(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   REGISTRATION SUBMISSION
========================================================= */

async function handleRegistration(event) {
    event.preventDefault();

    const elements = getAuthElements();

    const name =
        elements.registerName.value.trim();

    const email =
        elements.registerEmail.value
            .trim()
            .toLowerCase();

    const password =
        elements.registerPassword.value;

    showAuthMessage(
        "Creating your account…"
    );

    try {
        await registerUser(
            name,
            email,
            password
        );

        /*
         * Automatically sign the user in after successful
         * registration.
         */
        const user =
            await loginWithEmail(
                email,
                password
            );

        elements.registerForm.reset();

        showDashboard(
            user,
            "local"
        );

    } catch (error) {
        console.error(
            "Registration error:",
            error
        );

        showAuthMessage(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   LOGOUT
========================================================= */

function handleLogout() {
    if (
        currentAuthType === "github"
    ) {
        /*
         * Azure Static Web Apps logout.
         */
        window.location.href =
            "/.auth/logout?post_logout_redirect_uri=/";

        return;
    }

    /*
     * Local JWT logout.
     */
    sessionStorage.removeItem(
        TOKEN_KEY
    );

    showAuthScreen();

    showAuthMessage(
        "You have been signed out."
    );
}


/* =========================================================
   START
========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    () => {
        const elements = getAuthElements();

        elements.showLoginButton.addEventListener(
            "click",
            showLoginForm
        );

        elements.showRegisterButton.addEventListener(
            "click",
            showRegisterForm
        );

        elements.loginForm.addEventListener(
            "submit",
            handleLogin
        );

        elements.registerForm.addEventListener(
            "submit",
            handleRegistration
        );

        elements.logoutButton.addEventListener(
            "click",
            handleLogout
        );

        initializeAuthentication();
    }
);