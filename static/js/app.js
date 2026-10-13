// EduEagle - Academic Workspace & Mentorship Companion
// Frontend Controller & State Management
// Built under NEP 2020 Academic Framework & DPDP Act 2023 Compliance

const API_BASE = "/api";
let demoAuthEnabled = false;

// Global Authenticated Fetch Interceptor (Attaches Bearer Token automatically)
const _originalFetch = window.fetch;
window.fetch = async function(url, options = {}) {
  const opts = options || {};
  const headers = new Headers(opts.headers || {});
  const token = sessionStorage.getItem("edueagle_auth_token") || 
                (state.currentUser ? `edueagle-token-${state.currentUser.id}` : "");
  if (token && typeof url === "string" && url.startsWith("/api/") && 
      !url.startsWith("/api/auth/otp/request") && !url.startsWith("/api/auth/login") &&
      !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await _originalFetch(url, { ...opts, headers });
  if (res.status === 401 && typeof url === "string" && url.startsWith("/api/") && !url.startsWith("/api/auth/")) {
    showLoginScreen();
  }
  return res;
};

const state = {
  currentUser: {
    id: "USR-002",
    name: "Dr. Priya Nair",
    email: "priya.nair@edueagle.edu",
    phone: "9811122233",
    role: "Faculty",
    department: "Computer Science & Engineering",
    avatar: "PN",
    student_id: null
  },
  allUsers: [],
  currentTab: "podium",
  isAuthenticated: false,
  token: null,

  // Module F: Podium & Marks Ledger
  podium: [],
  marksLedger: [],

  // Module A: Smart Attendance
  attendanceData: null,

  // Module D: Tasks & Submissions
  tasks: [],
  selectedUploadFile: null,

  // Module E: Academic Hub Resources
  resources: [],
  activeHubSubject: "All",

  // Module: Timed Assessments & Mock Tests
  mockTests: [],
  activeTest: null,
  testTimerInterval: null,
  testStartTime: null,
  testAnswers: {},
  testDurationSeconds: 0,
  testRemainingSeconds: 0,
  testHistory: [],

  // Module: Confidential Well-Being Support
  wellbeingHistory: [],

  // In-App Notification Center
  userNotifications: [],

  // Merit Reward Claims Desk
  rewardPoints: null,
  userClaims: [],

  // Assignment Appeals
  userAppeals: [],

  // Module B: Mentor Pulse & Review Schedule
  pulseFeed: [],
  pulseSchedule: null,
  reviewScheduleDay: "Friday",

  // Module C: Parent Portal 14-Day Digest
  parentDigest: null,

  // Fees & Complete Work Portfolio
  myFeeAccount: null,
  cohortFees: null,
  selectedPortfolioStudent: "STU-101",
  studentPortfolioData: null,

  // Legacy & Compatibility
  cohortStats: null,
  students: []
};

// Initialize Application
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const response = await fetch(`${API_BASE}/config`);
    if (response.ok) {
      const config = await response.json();
      demoAuthEnabled = config.demo_auth_enabled === true;
    }
  } catch (err) {
    console.error("Unable to load deployment authentication settings.", err);
  }
  applyDeploymentAuthMode();
  setupNavigation();
  checkAuthOnLoad();
  await loadInitialData();
});

function applyDeploymentAuthMode() {
  if (demoAuthEnabled) return;

  document.querySelectorAll(
    '[onclick*="quickLoginAs"], #institutional-quick-personas, ' +
    '#landing-tab-phone, #landing-tab-gmail, #pill-phone, #pill-gmail, ' +
    'a[onclick*="toggleStudentAuthView"], a[onclick*="switchLoginTab(\'phone\')"]'
  ).forEach((element) => {
    element.style.display = "none";
  });

  const loginSub = document.getElementById("gateway-login-sub");
  if (loginSub) {
    loginSub.textContent =
      "Sign in with your institution-provisioned email or student ID and password.";
  }
}

function checkAuthOnLoad() {
  const savedUser = sessionStorage.getItem("edueagle_auth_user");
  const savedToken = sessionStorage.getItem("edueagle_auth_token");
  if (savedUser && savedToken) {
    try {
      state.currentUser = JSON.parse(savedUser);
      state.token = savedToken;
      state.isAuthenticated = true;
      hideLoginScreen();
      updateUserUI();
    } catch (e) {
      showLoginScreen();
    }
  } else {
    state.isAuthenticated = false;
    showLoginScreen();
  }
}

function showLoginScreen() {
  const el = document.getElementById("login-screen");
  if (el) el.classList.remove("hidden");
  if (typeof updatePageMetadata === "function") updatePageMetadata("login");
  if (typeof switchGatewayMode === "function") switchGatewayMode("student");
}

function hideLoginScreen() {
  const el = document.getElementById("login-screen");
  if (el) el.classList.add("hidden");
  if (typeof updatePageMetadata === "function") updatePageMetadata(state.currentTab || "podium");
}

function logoutToLoginScreen() {
  sessionStorage.removeItem("edueagle_auth_user");
  sessionStorage.removeItem("edueagle_auth_token");
  state.token = null;
  state.isAuthenticated = false;
  showLoginScreen();
  showToast("You have signed out. Please sign in to continue.", "info", "Signed Out");
}

// ==========================================================================
// FORM ERROR STATES & LOADING HELPERS (Verified by Unit Tests)
// ==========================================================================

function showGlobalLoader(durationMs = 600) {
  const loader = document.getElementById("global-loader");
  if (!loader) return;
  loader.classList.add("is-active");
  loader.style.width = "35%";
  setTimeout(() => {
    if (loader.classList.contains("is-active")) loader.style.width = "75%";
  }, 150);
  setTimeout(() => {
    loader.style.width = "100%";
    setTimeout(() => {
      loader.classList.remove("is-active");
      loader.style.width = "0%";
    }, 200);
  }, durationMs);
}

function setBtnLoading(btnOrId, isLoading, loadingText = "") {
  const btn = typeof btnOrId === "string" ? document.getElementById(btnOrId) : btnOrId;
  if (!btn) return;
  if (isLoading) {
    btn.dataset.origHtml = btn.innerHTML;
    btn.classList.add("is-loading");
    btn.disabled = true;
    let spinner = btn.querySelector(".btn-spinner");
    if (!spinner) {
      spinner = document.createElement("span");
      spinner.className = "btn-spinner";
      btn.appendChild(spinner);
    }
  } else {
    btn.classList.remove("is-loading");
    btn.disabled = false;
    if (btn.dataset.origHtml) {
      btn.innerHTML = btn.dataset.origHtml;
    }
  }
}

function setFieldError(fieldOrId, errorMsg) {
  const field = typeof fieldOrId === "string" ? document.getElementById(fieldOrId) : fieldOrId;
  if (!field) return;
  clearFieldError(field);
  field.classList.add("has-error");

  const errDiv = document.createElement("div");
  errDiv.className = "field-error-msg";
  errDiv.id = `${field.id || 'field'}-error-msg`;
  errDiv.innerHTML = `
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2" aria-hidden="true">
      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
    <span>${errorMsg}</span>
  `;

  if (field.parentElement && field.parentElement.style.display === "flex") {
    field.parentElement.parentElement.appendChild(errDiv);
  } else if (field.nextSibling) {
    field.parentNode.insertBefore(errDiv, field.nextSibling);
  } else {
    field.parentNode.appendChild(errDiv);
  }

  field.addEventListener("input", function onInputClear() {
    clearFieldError(field);
    field.removeEventListener("input", onInputClear);
  });
}

function clearFieldError(fieldOrId) {
  const field = typeof fieldOrId === "string" ? document.getElementById(fieldOrId) : fieldOrId;
  if (!field) return;
  field.classList.remove("has-error");
  const fieldId = field.id || 'field';
  const existing = document.getElementById(`${fieldId}-error-msg`);
  if (existing) existing.remove();
  if (field.parentElement) {
    const parentErr = field.parentElement.querySelector(".field-error-msg");
    if (parentErr) parentErr.remove();
    if (field.parentElement.parentElement) {
      const gParentErr = field.parentElement.parentElement.querySelector(`#${fieldId}-error-msg`);
      if (gParentErr) gParentErr.remove();
    }
  }
}

// Landing Tabs Controller
function switchLoginTab(tab) {
  const credTab = document.getElementById("landing-tab-staff-cred");
  const phoneTab = document.getElementById("landing-tab-phone");
  const gmailTab = document.getElementById("landing-tab-gmail");

  if (credTab) credTab.style.display = tab === 'staff_cred' ? 'block' : 'none';
  if (phoneTab) phoneTab.style.display = tab === 'phone' ? 'block' : 'none';
  if (gmailTab) gmailTab.style.display = tab === 'gmail' ? 'block' : 'none';

  const pCred = document.getElementById("pill-staff-cred");
  const pPhone = document.getElementById("pill-phone");
  const pGmail = document.getElementById("pill-gmail");

  if (pCred) pCred.classList.toggle("active", tab === 'staff_cred');
  if (pPhone) pPhone.classList.toggle("active", tab === 'phone');
  if (pGmail) pGmail.classList.toggle("active", tab === 'gmail');
}

function fillDemoCredentials(role) {
  if (role === 'student') {
    switchGatewayMode('student');
    const idInput = document.getElementById("student-login-id");
    const pwdInput = document.getElementById("student-login-pwd");
    if (idInput) idInput.value = "21CS042";
    if (pwdInput) pwdInput.value = "student123";
    showToast("Student credentials loaded: 21CS042 / student123", "info", "Demo Credentials");
    if (idInput) {
      idInput.focus();
      idInput.style.outline = "2px solid var(--primary)";
      setTimeout(() => { if (idInput) idInput.style.outline = ""; }, 1500);
    }
  } else if (role === 'faculty') {
    switchGatewayMode('institutional');
    switchLoginTab('staff_cred');
    const idInput = document.getElementById("staff-login-id");
    const pwdInput = document.getElementById("staff-login-pwd");
    if (idInput) idInput.value = "priya.nair@edueagle.edu";
    if (pwdInput) pwdInput.value = "faculty123";
    showToast("Faculty credentials loaded: priya.nair@edueagle.edu / faculty123", "info", "Demo Credentials");
    if (idInput) {
      idInput.focus();
      idInput.style.outline = "2px solid var(--primary)";
      setTimeout(() => { if (idInput) idInput.style.outline = ""; }, 1500);
    }
  } else if (role === 'mentor') {
    switchGatewayMode('institutional');
    switchLoginTab('staff_cred');
    const idInput = document.getElementById("staff-login-id");
    const pwdInput = document.getElementById("staff-login-pwd");
    if (idInput) idInput.value = "rajesh.verma@edueagle.edu";
    if (pwdInput) pwdInput.value = "mentor123";
    showToast("Mentor credentials loaded: rajesh.verma@edueagle.edu / mentor123", "info", "Demo Credentials");
    if (idInput) {
      idInput.focus();
      idInput.style.outline = "2px solid var(--primary)";
      setTimeout(() => { if (idInput) idInput.style.outline = ""; }, 1500);
    }
  }
}

// Gateway Mode Controller (Student Portal vs Institutional Gateway)
function switchGatewayMode(mode) {
  const isStudent = mode === "student";
  const btnStu = document.getElementById("mode-btn-student");
  const btnInst = document.getElementById("mode-btn-institutional");
  const title = document.getElementById("gateway-login-title");
  const sub = document.getElementById("gateway-login-sub");
  const stuContainer = document.getElementById("student-login-form-container");
  const instContainer = document.getElementById("institutional-login-form-container");
  const instPersonas = document.getElementById("institutional-quick-personas");

  if (btnStu) {
    btnStu.classList.toggle("active", isStudent);
    btnStu.style.background = isStudent ? "#FFFFFF" : "transparent";
    btnStu.style.color = isStudent ? "var(--primary)" : "var(--text-muted)";
    btnStu.style.boxShadow = isStudent ? "var(--shadow-sm)" : "none";
  }
  if (btnInst) {
    btnInst.classList.toggle("active", !isStudent);
    btnInst.style.background = !isStudent ? "#FFFFFF" : "transparent";
    btnInst.style.color = !isStudent ? "var(--primary)" : "var(--text-muted)";
    btnInst.style.boxShadow = !isStudent ? "var(--shadow-sm)" : "none";
  }

  if (title) {
    title.textContent = isStudent ? "Student Portal Sign In" : "Institutional Gateway";
  }
  if (sub) {
    sub.textContent = isStudent 
      ? "Enter your University Roll Number / Student ID and password to access your academic workspace:"
      : "Authenticate with institutional staff credentials, OTP, or role profile:";
  }
  if (stuContainer) {
    stuContainer.style.display = isStudent ? "block" : "none";
  }
  if (instContainer) {
    instContainer.style.display = !isStudent ? "block" : "none";
  }
  if (instPersonas) {
    instPersonas.style.display = !isStudent ? "block" : "none";
  }
}

function activateStudentGatewayMode() {
  switchGatewayMode("student");
  const stuInput = document.getElementById("student-login-id");
  if (stuInput) {
    stuInput.focus();
    stuInput.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function focusSignInForm(mode) {
  if (mode === "student") {
    activateStudentGatewayMode();
  } else {
    switchGatewayMode("institutional");
    const staffInput = document.getElementById("landing-phone-input") || document.getElementById("landing-gmail-input");
    if (staffInput) {
      staffInput.focus();
      staffInput.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }
}

async function submitStudentLogin() {
  clearFieldError("student-login-id");
  clearFieldError("student-login-pwd");

  const idInput = document.getElementById("student-login-id");
  const pwdInput = document.getElementById("student-login-pwd");

  const identifier = idInput ? idInput.value.trim() : "";
  const password = pwdInput ? pwdInput.value.trim() : "";

  if (!identifier) {
    setFieldError("student-login-id", "Please enter your University Roll Number (e.g. 21CS042) or Student ID.");
    return;
  }

  setBtnLoading("btn-student-login", true, "Signing in...");
  showGlobalLoader(400);

  try {
    await handleAuthLogin({
      type: "credentials",
      identifier: identifier,
      password: password
    });
  } finally {
    setBtnLoading("btn-student-login", false);
  }
}

async function submitStaffLogin() {
  clearFieldError("staff-login-id");
  clearFieldError("staff-login-pwd");

  const idInput = document.getElementById("staff-login-id");
  const pwdInput = document.getElementById("staff-login-pwd");

  const identifier = idInput ? idInput.value.trim() : "";
  const password = pwdInput ? pwdInput.value.trim() : "";

  if (!identifier) {
    setFieldError("staff-login-id", "Please enter your Staff Email or Faculty ID.");
    return;
  }

  setBtnLoading("btn-staff-login", true, "Authenticating...");
  showGlobalLoader(400);

  try {
    await handleAuthLogin({
      type: "staff_login",
      identifier: identifier,
      password: password
    });
  } finally {
    setBtnLoading("btn-staff-login", false);
  }
}

function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPwd = input.type === "password";
  input.type = isPwd ? "text" : "password";
  if (btn) {
    btn.innerHTML = isPwd 
      ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
      : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
  }
}

function showStudentLoginHelp() {
  if (!demoAuthEnabled) {
    showToast("Use the account and password provisioned by your institution.", "info", "Institutional Sign In");
    return;
  }
  showToast("Demo Student Accounts: Enter Roll No 21CS042 (Aarav Sharma), 21EC019 (Riya Sen), or 22ME058 (Devansh Patel). Password: any password or student123.", "info", "Student Login Credentials");
}

// Phone + OTP Simulation
async function requestLandingPhoneOTP() {
  clearFieldError("landing-phone-input");
  const phoneInput = document.getElementById("landing-phone-input");
  const phone = phoneInput ? phoneInput.value.trim() : "";
  if (!phone || phone.length < 10 || !/^\d{10}$/.test(phone)) {
    setFieldError("landing-phone-input", "Please enter a valid 10-digit mobile number.");
    return;
  }
  setBtnLoading("landing-btn-send-otp", true, "Sending...");
  showGlobalLoader(400);
  try {
    const res = await fetch(`${API_BASE}/auth/otp/request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: phone })
    });
    const data = await res.json();
    if (data.success) {
      document.getElementById("landing-otp-group").style.display = "block";
      document.getElementById("landing-btn-send-otp").style.display = "none";
      document.getElementById("landing-btn-verify-otp").style.display = "inline-flex";
      document.getElementById("landing-otp-input").value = data.demo_otp || "123456";
      showToast(`Verification code sent! Demo OTP: ${data.demo_otp}`, "info", "OTP Sent");
    } else {
      setFieldError("landing-phone-input", data.error || "Failed to dispatch verification code.");
    }
  } catch (err) {
    showToast("Failed to request OTP. Please check connection.", "error");
  } finally {
    setBtnLoading("landing-btn-send-otp", false);
  }
}

async function verifyLandingPhoneLogin() {
  clearFieldError("landing-otp-input");
  const phone = document.getElementById("landing-phone-input").value.trim();
  const otpInput = document.getElementById("landing-otp-input");
  const otp = otpInput ? otpInput.value.trim() : "";
  if (!otp || otp.length < 6) {
    setFieldError("landing-otp-input", "Please enter the complete 6-digit verification code.");
    return;
  }
  setBtnLoading("landing-btn-verify-otp", true, "Verifying...");
  showGlobalLoader(500);
  try {
    await handleAuthLogin({ type: "phone", phone: phone, otp: otp });
  } finally {
    setBtnLoading("landing-btn-verify-otp", false);
  }
}

async function loginWithLandingGmail() {
  clearFieldError("landing-gmail-input");
  const emailInput = document.getElementById("landing-gmail-input");
  const email = emailInput ? emailInput.value.trim() : "";
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    setFieldError("landing-gmail-input", "Please enter a valid institutional email address.");
    return;
  }
  showGlobalLoader(400);
  await handleAuthLogin({ type: "gmail", email: email });
}

async function quickLoginAs(role) {
  if (!demoAuthEnabled) {
    showToast("Role-switch sign-in is disabled. Use your institution-provisioned account.", "error", "Sign In");
    return;
  }
  showGlobalLoader(300);
  await handleAuthLogin({ type: "role_switch", role: role });
}

async function handleAuthLogin(bodyPayload) {
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bodyPayload)
    });
    const data = await res.json();
    if (data.success) {
      state.currentUser = data.user;
      state.token = data.token;
      state.isAuthenticated = true;
      sessionStorage.setItem("edueagle_auth_user", JSON.stringify(data.user));
      sessionStorage.setItem("edueagle_auth_token", data.token);
      updateUserUI();
      hideLoginScreen();
      showToast(`Signed in successfully as ${data.user.name} (${data.user.role})`, "success", "Welcome to EduEagle");

      // Switch to default view and reload all module data
      switchTab("podium");
      await loadInitialData();
    } else {
      showToast(data.error || "Authentication failed. Please verify credentials.", "error", "Sign In Notice");
    }
  } catch (err) {
    showToast("Authentication request failed. Please check network connection.", "error", "Connection Error");
  }
}

// User UI & Role Badges
function updateUserUI() {
  const avatarEl = document.getElementById("header-user-avatar");
  const nameEl = document.getElementById("header-user-name");
  const roleEl = document.getElementById("header-user-role");

  if (avatarEl) avatarEl.textContent = state.currentUser.avatar || state.currentUser.name.substring(0, 2).toUpperCase();
  if (nameEl) nameEl.textContent = state.currentUser.name;
  if (roleEl) roleEl.textContent = `${state.currentUser.role}, ${state.currentUser.department || 'Academic'}`;

  // Role-adaptive visibility of navigation tabs
  const isStudent = state.currentUser.role === "Student";

  const tabStudentFees = document.getElementById("tab-student-fees");
  const tabInstitutionalFees = document.getElementById("tab-institutional-fees");
  const tabStudentsPortfolio = document.getElementById("tab-students-portfolio");
  const tabMentorPulse = document.getElementById("tab-mentor-pulse");
  const tabCohort = document.getElementById("tab-cohort");
  const tabSafeguards = document.getElementById("tab-safeguards");
  const btnEditProfile = document.getElementById("btn-edit-student-profile");
  const mockFacultyBtn = document.getElementById("mock-test-faculty-btn-wrap");
  const appealsPanel = document.getElementById("faculty-appeals-review-panel");

  if (tabStudentFees) tabStudentFees.style.display = isStudent ? "flex" : "none";
  if (tabInstitutionalFees) tabInstitutionalFees.style.display = isStudent ? "none" : "flex";
  if (tabStudentsPortfolio) tabStudentsPortfolio.style.display = isStudent ? "none" : "flex";
  if (tabMentorPulse) tabMentorPulse.style.display = isStudent ? "none" : "flex";
  if (tabCohort) tabCohort.style.display = isStudent ? "none" : "flex";
  if (tabSafeguards) tabSafeguards.style.display = isStudent ? "none" : "flex";
  if (btnEditProfile) btnEditProfile.style.display = isStudent ? "inline-flex" : "none";
  if (mockFacultyBtn) mockFacultyBtn.style.display = !isStudent ? "block" : "none";
  if (appealsPanel) appealsPanel.style.display = !isStudent ? "block" : "none";

  const podiumTabLabel = document.getElementById("tab-label-podium");
  if (podiumTabLabel) {
    podiumTabLabel.textContent = isStudent ? "Podium & My Marks" : "Podium & Marks";
  }

  const attTabLabel = document.getElementById("tab-label-attendance");
  if (attTabLabel) {
    attTabLabel.textContent = isStudent ? "My Attendance" : "Smart Attendance";
  }

  const tasksTabLabel = document.getElementById("tab-label-tasks");
  if (tasksTabLabel) {
    tasksTabLabel.textContent = isStudent ? "My Tasks & Submissions" : "Tasks & AI Integrity";
  }

  const parentTabLabel = document.getElementById("tab-label-parent");
  if (parentTabLabel) {
    parentTabLabel.textContent = isStudent ? "Parent Digest (14d)" : "Parent Digest Desk";
  }

  const chatRoleIndicator = document.getElementById("ai-chat-role-indicator");
  if (chatRoleIndicator) {
    chatRoleIndicator.textContent = isStudent ? "Student Academic Companion" : `${state.currentUser.role} Co-Pilot & Cohort Review`;
  }
}

// Navigation & Tab Switching
function setupNavigation() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const tabId = tab.getAttribute("data-tab");
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  state.currentTab = tabId;

  // Toggle active class on navigation tabs
  document.querySelectorAll(".nav-tab").forEach(tab => {
    tab.classList.toggle("active", tab.getAttribute("data-tab") === tabId);
  });

  // Toggle active view section
  document.querySelectorAll(".tab-view").forEach(view => {
    view.classList.toggle("active", view.id === `view-${tabId}`);
  });

  updatePageMetadata(tabId);
  window.scrollTo({ top: 0, behavior: "smooth" });

  // Trigger data render for the selected view
  if (tabId === "podium") renderPodiumView();
  else if (tabId === "attendance") renderAttendanceView();
  else if (tabId === "tasks") renderTasksView();
  else if (tabId === "mock_tests") renderMockTestsView();
  else if (tabId === "academic_hub") renderAcademicHubView();
  else if (tabId === "wellbeing") renderWellbeingView();
  else if (tabId === "student_fees") renderStudentFeeView();
  else if (tabId === "institutional_fees") renderInstitutionalFeeView();
  else if (tabId === "students") renderStudentPortfolioView();
  else if (tabId === "mentor_pulse") renderMentorPulseView();
  else if (tabId === "parent_portal") renderParentPortalView();
  else if (tabId === "cohort") renderCohortView();
}

// ==========================================================================
// VIEW METADATA (Required by SEO Test Suite)
// ==========================================================================

const VIEW_METADATA = {
  student_fees: {
    title: "Student Fee Ledger & Financial Transparency | EduEagle",
    description: "Transparent fee component breakdown, online payment gateway, and downloadable institutional receipts."
  },
  institutional_fees: {
    title: "Institutional Fee Management & Financial Governance | EduEagle",
    description: "Cohort fee collection intelligence, student fee ledgers, offline payment recording, and reminder dispatch."
  },
  login: {
    title: "EduEagle | Institutional Student Success & Early Warning System",
    description: "Enterprise student success and academic early warning system for universities, providing explainable risk attribution, automated intervention workflows, and FERPA-compliant governance."
  },
  podium: {
    title: "Academic Excellence Podium & Marks Ledger | EduEagle",
    description: "Top 3 scholars recognition podium with gold, silver, and bronze honours alongside continuous evaluation internal marks ledger."
  },
  attendance: {
    title: "Smart Attendance Tracker & Risk Engine | EduEagle",
    description: "Real-time student attendance monitoring with 3-tier risk categorisation and automated statutory 75 percent threshold alerts."
  },
  tasks: {
    title: "Task Studio & Manual AI Integrity Verification | EduEagle",
    description: "Coursework submissions with up to 80 MB drag-and-drop uploader and teacher-triggered manual AI originality verification."
  },
  academic_hub: {
    title: "Academic Resource Hub & Question-Driven AI Summarizer | EduEagle",
    description: "Semester lecture notes, syllabus guides, previous year question archive, and question-driven AI study summarizer."
  },
  mentor_pulse: {
    title: "Automated Mentor Pulse Feed & Review Scheduler | EduEagle",
    description: "Alternate-day pulse feed with off-day pausing and configurable weekly review digest schedule for academic mentors."
  },
  parent_portal: {
    title: "Parent Transparency Portal & 14-Day Bi-Weekly Digest | EduEagle",
    description: "Holistic 360 snapshot for parents covering academic trajectory, attendance velocity, and extracurricular achievements."
  },
  cohort: {
    title: "Cohort Analytics & Retention Dashboard | EduEagle",
    description: "Monitor real-time cohort retention, multi-factorial risk distributions, and academic warning indicators across departments."
  },
  students: {
    title: "Student 360 Academic Dossier Directory | EduEagle",
    description: "Comprehensive student academic profiles integrating continuous internal evaluations, attendance velocity, fee records, and advisor feedback."
  },
  workflows: {
    title: "Intervention Desk & Advisory Workflows | EduEagle",
    description: "Accountable intervention workflows dispatching faculty advisors, mentors, and counselors with defined SLAs and automated escalations."
  },
  outcomes: {
    title: "Outcome Verification & Proof Ledger | EduEagle",
    description: "Audited verification logs for academic retests, remedial attendance, and institutional intervention outcome measurements."
  },
  student_hub: {
    title: "Student Academic Advising & Support Portal | EduEagle",
    description: "Student self-service portal for inspecting academic risk metrics, managing parental notification consent, and submitting Beacon support requests."
  },
  safeguards: {
    title: "FERPA Compliance & Algorithmic Safeguards | EduEagle",
    description: "Institutional algorithmic governance guidelines ensuring non-punitive alert usage, human advisor overrides, and FERPA data protection."
  },
  mock_tests: {
    title: "Timed Assessments & Mock Tests | EduEagle",
    description: "Standardized timed assessments with live countdown timer, auto-submission, topic performance breakdown, and speed vs accuracy analytics."
  },
  wellbeing: {
    title: "Student Well-Being & Confidential Support | EduEagle",
    description: "Privacy-conscious student mood and well-being check-ins with campus counseling resources and non-clinical guidance."
  }
};

function updatePageMetadata(key) {
  const meta = VIEW_METADATA[key] || VIEW_METADATA.podium;
  document.title = meta.title;
  let descTag = document.querySelector('meta[name="description"]');
  if (!descTag) {
    descTag = document.createElement("meta");
    descTag.setAttribute("name", "description");
    document.head.appendChild(descTag);
  }
  descTag.setAttribute("content", meta.description);

  const ogTitle = document.querySelector('meta[property="og:title"]');
  if (ogTitle) ogTitle.setAttribute("content", meta.title);

  const ogDesc = document.querySelector('meta[property="og:description"]');
  if (ogDesc) ogDesc.setAttribute("content", meta.description);
}

// Toast notification helper
function showToast(message, type = "info", title = "") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  
  let iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0F5338" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
  if (type === "success") iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#15803D" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>';
  if (type === "warning") iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#D97706" stroke-width="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
  if (type === "error") iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';

  toast.innerHTML = `
    <span style="display: flex; align-items: center;">${iconSvg}</span>
    <div style="flex: 1;">
      ${title ? `<div style="font-weight: 700; font-size: 0.84rem; margin-bottom: 2px; color: var(--text-main);">${title}</div>` : ""}
      <div style="font-size: 0.8rem; color: var(--text-muted);">${message}</div>
    </div>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease-out";
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

// ==========================================================================
// DATA FETCHING CONTROLLER
// ==========================================================================

async function loadInitialData() {
  await Promise.all([
    fetchPodiumAndMarks(),
    fetchAttendanceData(),
    fetchTasks(),
    fetchAcademicResources(),
    fetchMentorPulse(),
    fetchMentorReviewSchedule(),
    fetchParentDigest(),
    fetchFeeData(),
    fetchStudentsPortfolio(),
    fetchNotifications(),
    fetchMockTests(),
    fetchRewardClaimsDesk(),
    (state.currentUser && state.currentUser.role !== "Student" ? fetchAppeals() : Promise.resolve())
  ]);
}

// ==========================================================================
// MODULE F: TOP 3 PODIUM & EDITABLE MARKS LEDGER
// ==========================================================================

async function fetchPodiumAndMarks() {
  try {
    const res = await fetch(`${API_BASE}/podium-and-marks`);
    const data = await res.json();
    state.podium = data.top_podium || [];
    state.marksLedger = data.marks_ledger || [];
    renderPodiumView();
  } catch (err) {
    console.error("Error fetching podium and marks:", err);
  }
}

function renderPodiumView() {
  const container = document.getElementById("podium-cards-container");
  if (!container) return;

  if (!state.podium || state.podium.length < 3) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 24px; color: var(--text-muted);">Loading Academic Podium...</div>`;
    return;
  }

  const p1 = state.podium[0]; // Gold
  const p2 = state.podium[1]; // Silver
  const p3 = state.podium[2]; // Bronze

  container.innerHTML = `
    <!-- 2nd Rank: Silver -->
    <div class="podium-card podium-rank-2">
      <div class="podium-avatar">${p2.avatar || 'RI'}</div>
      <div class="podium-badge-pill badge-silver">2nd Rank - Silver Scholar</div>
      <div class="podium-name">${p2.name}</div>
      <div class="podium-roll">Roll: ${p2.roll_no}</div>
      <div class="podium-score-box">
        <div class="podium-score-val">${p2.total_marks} / 400</div>
        <div class="podium-score-label">${p2.percentage}% Aggregate</div>
      </div>
      <div style="display: flex; flex-direction: column; gap: 6px; margin-top: 10px; width: 100%;">
        <div class="podium-reward-tag" style="background: var(--bg-card); color: var(--text-main); border-color: var(--border-color); justify-content: space-between;">
          <span style="font-weight: 700; color: var(--text-main);">💰 Cash Prize:</span>
          <strong>INR 25,000</strong>
        </div>
        <div class="podium-reward-tag" style="background: var(--primary-light); color: var(--primary); border-color: var(--primary-border); justify-content: space-between;">
          <span style="font-weight: 700;">🎓 Tuition Waiver:</span>
          <strong>50% Concession</strong>
        </div>
        <div class="podium-reward-tag" style="font-size: 0.72rem; color: var(--text-muted);">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/></svg>
          <span>Priority Corporate Internship Referral</span>
        </div>
      </div>
      <button class="btn btn-secondary btn-sm" onclick="openTop3LaureateSubpage('${p2.student_id}')" style="margin-top: 10px; width: 100%; font-size: 0.72rem; justify-content: center;">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        <span>View Award Certificate</span>
      </button>
    </div>

    <!-- 1st Rank: Gold -->
    <div class="podium-card podium-rank-1">
      <div class="podium-crown-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7zm3 16h14v2H5v-2z"/></svg>
      </div>
      <div class="podium-avatar">${p1.avatar || 'DP'}</div>
      <div class="podium-badge-pill badge-gold">1st Rank - Gold Laureate</div>
      <div class="podium-name" style="font-size: 1.15rem;">${p1.name}</div>
      <div class="podium-roll">Roll: ${p1.roll_no}</div>
      <div class="podium-score-box" style="background: #FEF3C7;">
        <div class="podium-score-val" style="color: #92400E;">${p1.total_marks} / 400</div>
        <div class="podium-score-label" style="color: #B45309;">${p1.percentage}% Aggregate</div>
      </div>
      <div style="display: flex; flex-direction: column; gap: 6px; margin-top: 10px; width: 100%;">
        <div class="podium-reward-tag" style="background: #FEF3C7; border-color: #FDE68A; color: #92400E; justify-content: space-between;">
          <span style="font-weight: 700;">💰 Cash Prize:</span>
          <strong>INR 50,000 Grant</strong>
        </div>
        <div class="podium-reward-tag" style="background: var(--primary-light); color: var(--primary); border-color: var(--primary-border); justify-content: space-between;">
          <span style="font-weight: 700;">🎓 Tuition Waiver:</span>
          <strong>100% Free Tuition</strong>
        </div>
        <div class="podium-reward-tag" style="font-size: 0.72rem; color: #92400E; background: #FFFBEB; border-color: #FDE68A;">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.45 1-1 1H7v4h10v-4h-2c-.55 0-1-.45-1-1v-2.34c3-.9 5-3.66 5-6.66V4H6v4c0 3 2 5.76 5 6.66z"/></svg>
          <span>Dr. Kalam Presidential Gold Medal</span>
        </div>
      </div>
      <button class="btn btn-primary btn-sm" onclick="openTop3LaureateSubpage('${p1.student_id}')" style="margin-top: 10px; width: 100%; font-size: 0.72rem; justify-content: center;">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        <span>View Official Certificate &amp; Voucher</span>
      </button>
    </div>

    <!-- 3rd Rank: Bronze -->
    <div class="podium-card podium-rank-3">
      <div class="podium-avatar">${p3.avatar || 'AV'}</div>
      <div class="podium-badge-pill badge-bronze">3rd Rank - Bronze Laureate</div>
      <div class="podium-name">${p3.name}</div>
      <div class="podium-roll">Roll: ${p3.roll_no}</div>
      <div class="podium-score-box">
        <div class="podium-score-val">${p3.total_marks} / 400</div>
        <div class="podium-score-label">${p3.percentage}% Aggregate</div>
      </div>
      <div style="display: flex; flex-direction: column; gap: 6px; margin-top: 10px; width: 100%;">
        <div class="podium-reward-tag" style="background: var(--bg-card); color: var(--text-main); border-color: var(--border-color); justify-content: space-between;">
          <span style="font-weight: 700; color: var(--accent-terracotta);">💰 Cash Prize:</span>
          <strong>INR 10,000</strong>
        </div>
        <div class="podium-reward-tag" style="background: var(--primary-light); color: var(--primary); border-color: var(--primary-border); justify-content: space-between;">
          <span style="font-weight: 700;">🎓 Tuition Waiver:</span>
          <strong>25% Concession</strong>
        </div>
        <div class="podium-reward-tag" style="font-size: 0.72rem; color: var(--text-muted);">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/></svg>
          <span>Dean's Academic Book &amp; Cloud Grant</span>
        </div>
      </div>
      <button class="btn btn-secondary btn-sm" onclick="openTop3LaureateSubpage('${p3.student_id}')" style="margin-top: 10px; width: 100%; font-size: 0.72rem; justify-content: center;">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        <span>View Award Certificate</span>
      </button>
    </div>
  `;

  // Render Marks Ledger Table
  renderMarksLedgerTable();
}

let activeVoucherCode = "";
let activeLaureateStudentId = "";
let activeLaureateCertId = "";

async function openTop3LaureateSubpage(target) {
  showGlobalLoader(300);
  try {
    let studentId = "";
    if (typeof target === "number") {
      // Numerical rank: 1, 2, or 3
      if (target === 1) {
        studentId = (state.podium && state.podium[0]) ? state.podium[0].student_id : "STU-107";
      } else if (target === 2) {
        studentId = (state.podium && state.podium[1]) ? state.podium[1].student_id : "STU-108";
      } else if (target === 3) {
        studentId = (state.podium && state.podium[2]) ? state.podium[2].student_id : "STU-101";
      } else if (state.marksLedger && state.marksLedger[target - 1]) {
        studentId = state.marksLedger[target - 1].student_id;
      } else {
        studentId = "STU-107";
      }
    } else if (typeof target === "string") {
      studentId = target;
    }

    if (!studentId) {
      showToast("Scholar record identifier not provided.", "error");
      return;
    }

    const res = await fetch(`/api/scholarships/certificate/${studentId}`, {
      headers: getAuthHeaders()
    });

    if (!res.ok) {
      showToast("Unable to fetch laureate scholarship dossier.", "error");
      return;
    }

    const data = await res.json();
    const cert = data.certificate;

    // Check if scholar is Top 3 Laureate (Rank 1, 2, or 3)
    if (!cert.is_podium_laureate || cert.rank > 3) {
      // STRICTLY RESTRICTED TO TOP 3 ONLY
      renderTop3RestrictedModal(cert);
      openModal("modal-top3-restricted");
      showToast(
        `Reward Sub-Page restricted strictly to Top 3 scholars. ${cert.student_name} holds Rank #${cert.rank}.`,
        "warning",
        "Top 3 Laureate Access Only"
      );
      return;
    }

    // Scholar is authenticated Top 3 Laureate!
    activeLaureateStudentId = cert.student_id;
    activeLaureateCertId = cert.certificate_id;
    renderScholarshipCertificateModal(cert);
    openModal("scholarship-cert-modal");
  } catch (err) {
    showToast("Network error opening laureate sub-page.", "error");
  }
}

// Backward compatible alias
async function openScholarshipCertificateModal(studentId) {
  return openTop3LaureateSubpage(studentId);
}

function renderTop3RestrictedModal(cert) {
  const container = document.getElementById("top3-restricted-body");
  if (!container) return;

  const currentRank = cert.rank || 4;
  const p3 = (state.podium && state.podium[2]) || { percentage: 91.25, name: "Aarav Sharma" };
  const cutoffDiff = Math.max(0.5, (p3.percentage - (cert.avg_score || 88.0))).toFixed(1);

  container.innerHTML = `
    <div style="background: #FFFFFF; border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 18px; margin-bottom: 16px;">
      <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
        <div style="width: 44px; height: 44px; border-radius: 50%; background: var(--bg-sand); border: 2px solid var(--border-color); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 1rem; color: var(--text-main);">
          ${cert.student_name ? cert.student_name.split(' ').map(n=>n[0]).join('').substring(0,2) : 'ST'}
        </div>
        <div>
          <div style="font-weight: 800; font-size: 1.05rem; color: var(--text-main);">${cert.student_name}</div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">
            Roll No: <code>${cert.roll_no}</code> &bull; ${cert.department}
          </div>
        </div>
        <div style="margin-left: auto; text-align: right;">
          <span class="badge" style="background: #FEE2E2; color: #DC2626; border: 1px solid #FCA5A5; font-weight: 700;">
            Rank #${currentRank}
          </span>
        </div>
      </div>

      <div style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: var(--radius-sm); padding: 12px; margin-bottom: 14px; font-size: 0.8rem; color: #92400E; line-height: 1.5;">
        <strong>Statutory Eligibility Criterion (NEP 2020 Framework):</strong><br>
        Under university regulations, 100%, 50%, and 25% tuition fee waiver scholarships and cash grants (INR 50,000 / INR 25,000 / INR 10,000) are statutory honors strictly conferred upon the <strong>Top 3 eligible scholars</strong> on the Continuous Evaluation Podium.
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.78rem;">
        <div style="background: var(--bg-inset); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 10px;">
          <div style="color: var(--text-muted); font-size: 0.72rem;">Current Scholar Standing</div>
          <div style="font-weight: 800; font-size: 0.95rem; color: var(--text-main); margin-top: 2px;">Rank #${currentRank}</div>
          <div style="color: var(--text-muted); font-size: 0.72rem; margin-top: 2px;">Diligence Commendation</div>
        </div>
        <div style="background: var(--bg-inset); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 10px;">
          <div style="color: var(--text-muted); font-size: 0.72rem;">Top 3 Cutoff (Bronze Distinction)</div>
          <div style="font-weight: 800; font-size: 0.95rem; color: var(--primary); margin-top: 2px;">${p3.percentage}% (${p3.name})</div>
          <div style="color: var(--text-muted); font-size: 0.72rem; margin-top: 2px;">Cutoff gap: ~${cutoffDiff}% marks</div>
        </div>
      </div>
    </div>

    <div style="font-size: 0.8rem; color: var(--text-muted); line-height: 1.5;">
      <strong style="color: var(--text-main);">How to Unlock Top 3 Laureate Status:</strong>
      <ul style="margin: 6px 0 0 16px; padding: 0;">
        <li>Submit pending handwritten assignments with high rubric fidelity.</li>
        <li>Participate in timed mock assessments and improve problem-solving speed.</li>
        <li>Academic rankings recalculate in real-time as faculty submit internal marks.</li>
      </ul>
    </div>
  `;
}

function renderScholarshipCertificateModal(cert) {
  const body = document.getElementById("scholarship-cert-body");
  if (!body) return;

  activeVoucherCode = cert.bursary_credit_voucher || `VOUCHER-${cert.student_id}-2026`;

  // Find continuous evaluation marks for this student from state
  const row = (state.marksLedger || []).find(m => m.student_id === cert.student_id) || {
    data_structures: cert.rank === 1 ? 98 : cert.rank === 2 ? 94 : 92,
    operating_systems: cert.rank === 1 ? 96 : cert.rank === 2 ? 91 : 89,
    dbms: cert.rank === 1 ? 99 : cert.rank === 2 ? 95 : 94,
    computer_networks: cert.rank === 1 ? 96 : cert.rank === 2 ? 92 : 90,
    total_marks: cert.rank === 1 ? 389 : cert.rank === 2 ? 372 : 365,
    percentage: cert.rank === 1 ? 97.25 : cert.rank === 2 ? 93.13 : 91.25
  };

  body.innerHTML = `
    <div style="background: #FFFFFF; border: 2px solid var(--border-color); border-radius: var(--radius-md); padding: 22px; position: relative; box-shadow: var(--shadow-sm);">
      <!-- Certificate Header Banner -->
      <div style="text-align: center; border-bottom: 2px solid var(--primary); padding-bottom: 14px; margin-bottom: 18px;">
        <div style="display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 6px;">
          <div style="width: 28px; height: 28px; border-radius: 6px; background: var(--primary); color: #FFFFFF; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.85rem;">EE</div>
          <span style="font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 1.15rem; color: var(--text-main); letter-spacing: -0.02em;">EduEagle Academic Hub</span>
        </div>
        <div style="font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); font-weight: 700;">
          ${cert.statutory_framework}
        </div>
        <h2 style="font-size: 1.25rem; color: var(--primary); margin: 8px 0 4px 0; font-family: 'Plus Jakarta Sans', sans-serif;">
          Official Top 3 Laureate Dossier &amp; Scholarship Grant
        </h2>
        <div style="font-size: 0.76rem; color: var(--text-subtle);">
          Certificate Identifier: <code>${cert.certificate_id}</code> &bull; Issued: ${cert.issued_date}
        </div>
      </div>

      <!-- Scholar Details -->
      <div style="text-align: center; margin-bottom: 18px;">
        <p style="font-size: 0.82rem; color: var(--text-muted); margin: 0 0 4px 0;">This statutory grant is conferred upon</p>
        <h3 style="font-size: 1.35rem; color: var(--text-main); margin: 0 0 4px 0;">${cert.student_name}</h3>
        <div style="font-size: 0.82rem; color: var(--primary); font-weight: 600;">
          University Roll No: <code>${cert.roll_no}</code> &bull; ${cert.department} &bull; Academic Cycle ${cert.academic_year}
        </div>
        <div style="display: inline-block; margin-top: 8px; padding: 4px 14px; background: var(--bg-sand); border-radius: var(--radius-sm); font-size: 0.82rem; font-weight: 700; color: var(--text-main); border: 1px solid var(--border-color);">
          Honor Standing: Rank #${cert.rank} &bull; ${cert.honor_title}
        </div>
      </div>

      <!-- Award Benefits Cards -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;">
        <!-- Tuition Fee Waiver Card -->
        <div style="background: var(--bg-inset); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 12px;">
          <div style="display: flex; align-items: center; gap: 6px; font-weight: 700; font-size: 0.78rem; color: var(--primary); margin-bottom: 4px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
            <span>TUITION SCHOLARSHIP</span>
          </div>
          <div style="font-size: 0.95rem; font-weight: 800; color: var(--text-main); margin-bottom: 2px;">
            ${cert.tuition_waiver}
          </div>
          <div style="font-size: 0.72rem; color: var(--text-muted);">
            Applied automatically against semester tuition liability in the university Bursar portal.
          </div>
        </div>

        <!-- Cash Prize Card -->
        <div style="background: var(--bg-inset); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 12px;">
          <div style="display: flex; align-items: center; gap: 6px; font-weight: 700; font-size: 0.78rem; color: var(--accent-terracotta); margin-bottom: 4px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/></svg>
            <span>DIRECT CASH PRIZE</span>
          </div>
          <div style="font-size: 0.95rem; font-weight: 800; color: var(--text-main); margin-bottom: 2px;">
            ${cert.cash_prize}
          </div>
          <div style="font-size: 0.72rem; color: var(--text-muted);">
            ${cert.disbursal_method} (${cert.disbursal_status}).
          </div>
        </div>
      </div>

      <!-- Verified NEP 2020 Continuous Evaluation Scorecard -->
      <div style="background: var(--bg-sand); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 12px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <span style="font-size: 0.76rem; font-weight: 700; color: var(--text-main); text-transform: uppercase; letter-spacing: 0.05em;">
            Verified Continuous Assessment Scorecard
          </span>
          <span style="font-size: 0.72rem; font-weight: 700; color: var(--primary);">
            Aggregate: ${row.percentage}% (${row.total_marks}/400)
          </span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; text-align: center; font-size: 0.74rem;">
          <div style="background: #FFFFFF; border: 1px solid var(--border-color); border-radius: 4px; padding: 6px;">
            <div style="color: var(--text-muted); font-size: 0.68rem;">Data Struct</div>
            <div style="font-weight: 800; color: var(--text-main); font-size: 0.88rem; margin-top: 2px;">${row.data_structures}/100</div>
          </div>
          <div style="background: #FFFFFF; border: 1px solid var(--border-color); border-radius: 4px; padding: 6px;">
            <div style="color: var(--text-muted); font-size: 0.68rem;">Operating Sys</div>
            <div style="font-weight: 800; color: var(--text-main); font-size: 0.88rem; margin-top: 2px;">${row.operating_systems}/100</div>
          </div>
          <div style="background: #FFFFFF; border: 1px solid var(--border-color); border-radius: 4px; padding: 6px;">
            <div style="color: var(--text-muted); font-size: 0.68rem;">DBMS</div>
            <div style="font-weight: 800; color: var(--text-main); font-size: 0.88rem; margin-top: 2px;">${row.dbms}/100</div>
          </div>
          <div style="background: #FFFFFF; border: 1px solid var(--border-color); border-radius: 4px; padding: 6px;">
            <div style="color: var(--text-muted); font-size: 0.68rem;">Networks</div>
            <div style="font-weight: 800; color: var(--text-main); font-size: 0.88rem; margin-top: 2px;">${row.computer_networks}/100</div>
          </div>
        </div>
      </div>

      ${cert.bursary_credit_voucher ? `
        <div style="background: var(--primary-light); border: 1px dashed var(--primary-border); border-radius: var(--radius-sm); padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <div>
            <div style="font-size: 0.72rem; font-weight: 700; color: var(--primary); text-transform: uppercase;">Official Bursary Concession Voucher</div>
            <code style="font-size: 0.9rem; font-weight: 800; color: var(--primary);">${cert.bursary_credit_voucher}</code>
          </div>
          <div style="display: flex; gap: 6px; align-items: center;">
            <span class="badge" style="background: #FFFFFF; color: var(--primary); border: 1px solid var(--primary-border); font-size: 0.72rem; font-weight: 700;">VERIFIED ACTIVE</span>
            <button class="btn btn-outline-primary btn-sm" onclick="claimScholarshipReward('${cert.student_id}', '${cert.certificate_id}')" id="btn-claim-reward" style="font-size: 0.72rem; padding: 3px 8px;">
              <span>Confirm Disbursal</span>
            </button>
          </div>
        </div>
      ` : ''}

      <!-- Statutory Signatures & Institutional Seal -->
      <div style="display: flex; justify-content: space-between; align-items: flex-end; padding-top: 12px; border-top: 1px solid var(--border-color); font-size: 0.74rem; color: var(--text-muted);">
        <div>
          <div style="font-weight: 700; color: var(--text-main);">Dr. Priya Nair</div>
          <div>Head, Academic Evaluation Board</div>
        </div>
        <div style="text-align: center;">
          <div style="width: 42px; height: 42px; border-radius: 50%; border: 2px solid var(--accent-gold); color: var(--accent-gold); display: inline-flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.65rem;">
            SEAL
          </div>
          <div style="font-size: 0.68rem; margin-top: 2px;">NEP 2020</div>
        </div>
        <div style="text-align: right;">
          <div style="font-weight: 700; color: var(--text-main);">Prof. K. R. Ramanathan</div>
          <div>Dean &amp; Registrar of Academic Affairs</div>
        </div>
      </div>
    </div>
  `;
}

function claimScholarshipReward(studentId, certId) {
  const btn = document.getElementById("btn-claim-reward");
  if (btn) {
    btn.innerHTML = `<span>Claimed &amp; Disbursed</span>`;
    btn.classList.remove("btn-outline-primary");
    btn.classList.add("btn-primary");
    btn.disabled = true;
  }
  showToast(
    `Statutory grant successfully acknowledged for scholar ${studentId}! Bursary Voucher: ${activeVoucherCode}`,
    "success",
    "Scholarship Disbursed"
  );
}

function printOrDownloadCertificate() {
  window.print();
}

function copyVoucherCode() {
  if (navigator.clipboard && activeVoucherCode) {
    navigator.clipboard.writeText(activeVoucherCode);
  }
  showToast(`Voucher code copied: ${activeVoucherCode}`, "success", "Voucher Ready");
}

function renderMarksLedgerTable() {
  const tbody = document.getElementById("marks-ledger-tbody");
  const thAction = document.getElementById("marks-th-action");
  const noteEl = document.getElementById("marks-ledger-role-note");
  if (!tbody) return;

  const isStudent = state.currentUser.role === "Student";

  if (noteEl) {
    noteEl.textContent = isStudent 
      ? "Student Mode (Read-Only): Viewing authenticated academic scores. Edit controls are restricted to appointed faculty."
      : "Faculty / Mentor Mode: Edit marks inline and click Save to instantly recalculate totals and live re-rank the podium.";
  }

  if (thAction) {
    thAction.style.display = isStudent ? "none" : "table-cell";
  }

  tbody.innerHTML = state.marksLedger.map((row, idx) => {
    const isCurrent = isStudent && (row.student_id === state.currentUser.student_id || row.student_id === "STU-101");
    const highlight = isCurrent ? `style="background: var(--primary-light);"` : "";
    const rankNum = row.current_rank || idx + 1;
    const isTop3 = rankNum <= 3;
    const rankBadge = isTop3 
      ? `<span class="badge" style="background: var(--accent-gold-light); color: var(--accent-gold); font-size: 0.65rem; margin-left: 6px; cursor: pointer;" onclick="openTop3LaureateSubpage('${row.student_id}')" title="Top 3 Scholar: View Statutory Reward Dossier">Top 3 Laureate &rarr;</span>`
      : `<span class="badge" style="background: var(--bg-sand); color: var(--text-muted); font-size: 0.65rem; margin-left: 6px; cursor: pointer;" onclick="openTop3LaureateSubpage('${row.student_id}')" title="Click to view reward eligibility">Rank #${rankNum}</span>`;

    if (isStudent) {
      // STRICTLY READ-ONLY FOR STUDENTS: No input elements in DOM
      return `
        <tr ${highlight}>
          <td>
            <a href="javascript:void(0)" onclick="openTop3LaureateSubpage('${row.student_id}')" style="font-weight: 700; color: var(--primary);" title="Click to view reward status">
              #${rankNum}
            </a>
          </td>
          <td>
            <div style="font-weight: 700;">
              <a href="javascript:void(0)" onclick="openTop3LaureateSubpage('${row.student_id}')" style="color: inherit; text-decoration: none;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">
                ${row.student_name}
              </a>
              ${isCurrent ? '<span style="font-size: 0.72rem; color: var(--primary); font-weight: 700;">(You)</span>' : ''}
              ${rankBadge}
            </div>
          </td>
          <td><code>${row.roll_no}</code></td>
          <td>${row.data_structures}</td>
          <td>${row.operating_systems}</td>
          <td>${row.dbms}</td>
          <td>${row.computer_networks}</td>
          <td><strong>${row.total_marks} / 400</strong></td>
          <td><span style="font-weight: 700; color: var(--primary);">${row.percentage}%</span></td>
        </tr>
      `;
    }

    // FACULTY / MENTOR: Full inline editable controls
    return `
      <tr id="marks-row-${row.student_id}">
        <td>
          <a href="javascript:void(0)" onclick="openTop3LaureateSubpage('${row.student_id}')" style="font-weight: 700; color: var(--primary);" title="Click to view reward status">
            #${rankNum}
          </a>
        </td>
        <td>
          <div style="font-weight: 700;">
            <a href="javascript:void(0)" onclick="openTop3LaureateSubpage('${row.student_id}')" style="color: inherit; text-decoration: none;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">
              ${row.student_name}
            </a>
            ${rankBadge}
          </div>
        </td>
        <td><code>${row.roll_no}</code></td>
        <td><input type="number" class="mark-input-editable" id="mark-ds-${row.student_id}" value="${row.data_structures}" min="0" max="100"></td>
        <td><input type="number" class="mark-input-editable" id="mark-os-${row.student_id}" value="${row.operating_systems}" min="0" max="100"></td>
        <td><input type="number" class="mark-input-editable" id="mark-dbms-${row.student_id}" value="${row.dbms}" min="0" max="100"></td>
        <td><input type="number" class="mark-input-editable" id="mark-cn-${row.student_id}" value="${row.computer_networks}" min="0" max="100"></td>
        <td><strong id="mark-total-${row.student_id}">${row.total_marks} / 400</strong></td>
        <td><span style="font-weight: 700; color: var(--primary);" id="mark-pct-${row.student_id}">${row.percentage}%</span></td>
        <td>
          <button class="btn btn-primary btn-sm" id="btn-save-marks-${row.student_id}" onclick="saveStudentMarks('${row.student_id}')">
            <span>Save &amp; Recalculate</span>
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

async function saveStudentMarks(studentId) {
  const dsInput = document.getElementById(`mark-ds-${studentId}`);
  const osInput = document.getElementById(`mark-os-${studentId}`);
  const dbmsInput = document.getElementById(`mark-dbms-${studentId}`);
  const cnInput = document.getElementById(`mark-cn-${studentId}`);

  if (!dsInput || !osInput || !dbmsInput || !cnInput) return;

  const payload = {
    student_id: studentId,
    data_structures: parseInt(dsInput.value, 10),
    operating_systems: parseInt(osInput.value, 10),
    dbms: parseInt(dbmsInput.value, 10),
    computer_networks: parseInt(cnInput.value, 10)
  };

  setBtnLoading(`btn-save-marks-${studentId}`, true, "Saving...");
  showGlobalLoader(500);

  try {
    const res = await fetch(`${API_BASE}/marks/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Marks updated for ${studentId}. Live podium re-ranked!`, "success", "Academic Ledger Updated");
      // Instant recalculation: update total in row
      const totalEl = document.getElementById(`mark-total-${studentId}`);
      const pctEl = document.getElementById(`mark-pct-${studentId}`);
      if (totalEl) totalEl.textContent = `${data.recalculated.total_marks} / 400`;
      if (pctEl) pctEl.textContent = `${data.recalculated.percentage}%`;

      // Refresh podium and full ledger from server
      await fetchPodiumAndMarks();
    } else {
      showToast(data.error || "Failed to update marks.", "error");
    }
  } catch (err) {
    showToast("Error updating marks ledger.", "error");
  } finally {
    setBtnLoading(`btn-save-marks-${studentId}`, false);
  }
}

// ==========================================================================
// MODULE A: SMART ATTENDANCE TRACKER & 3-TIER RISK ENGINE
// ==========================================================================

async function fetchAttendanceData() {
  try {
    const res = await fetch(`${API_BASE}/attendance`);
    state.attendanceData = await res.json();
    renderAttendanceView();
  } catch (err) {
    console.error("Error fetching attendance:", err);
  }
}

function renderAttendanceView() {
  if (!state.attendanceData) return;

  const alertContainer = document.getElementById("attendance-threshold-alert-container");
  const cardsGrid = document.getElementById("attendance-cards-grid");
  const tbody = document.getElementById("attendance-table-tbody");
  const riskFilter = document.getElementById("attendance-risk-filter") ? document.getElementById("attendance-risk-filter").value : "All";

  // Check 75% threshold alert
  const below75 = state.attendanceData.students_below_threshold || [];
  if (alertContainer) {
    if (below75.length > 0) {
      const topAlert = below75[0];
      alertContainer.innerHTML = `
        <div class="attendance-alert-card">
          <div class="attendance-alert-info">
            <div class="attendance-alert-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            </div>
            <div class="attendance-alert-text">
              <h5>Statutory Attendance Alert: Dropped Below 75% Threshold</h5>
              <p>Student <strong>${topAlert.student_name}</strong> (${topAlert.roll_no}) currently stands at <strong>${topAlert.attendance_overall}%</strong> overall attendance. Direct mentor intervention required.</p>
            </div>
          </div>
          <div>
            <button class="btn btn-danger btn-sm" onclick="dispatchAttendanceAlert('${topAlert.student_id}', 'Overall Coursework')">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 17H2a3 3 0 0 0 3-3V9a7 7 0 0 1 14 0v5a3 3 0 0 0 3 3zm-8.27 4a2 2 0 0 1-3.46 0"/></svg>
              <span>Dispatch Alert to Mentor</span>
            </button>
          </div>
        </div>
      `;
    } else {
      alertContainer.innerHTML = "";
    }
  }

  // Render Subject Cards
  const subjects = state.attendanceData.subject_breakdowns || [
    { subject: "Data Structures & Algorithms", code: "CS-301", attendance: 88, attended: 44, conducted: 50, risk: "Safe" },
    { subject: "Operating Systems", code: "CS-302", attendance: 72, attended: 36, conducted: 50, risk: "Low" },
    { subject: "Database Management Systems", code: "CS-303", attendance: 58, attended: 29, conducted: 50, risk: "Medium" },
    { subject: "Computer Networks", code: "CS-304", attendance: 46, attended: 23, conducted: 50, risk: "High" }
  ];

  if (cardsGrid) {
    cardsGrid.innerHTML = subjects.map(s => {
      let riskBadgeClass = "badge-risk-safe";
      let riskLabel = "On Track";
      let fillClass = "var(--risk-safe)";

      if (s.attendance < 50) {
        riskBadgeClass = "badge-risk-high";
        riskLabel = "High Risk (<50%)";
        fillClass = "var(--risk-high)";
      } else if (s.attendance < 60) {
        riskBadgeClass = "badge-risk-med";
        riskLabel = "Medium Risk (50-59.9%)";
        fillClass = "var(--risk-med)";
      } else if (s.attendance < 75) {
        riskBadgeClass = "badge-risk-low";
        riskLabel = "Low Risk (60-74.9%)";
        fillClass = "var(--risk-low)";
      }

      return `
        <div class="attendance-card">
          <div class="attendance-card-header">
            <div>
              <div class="attendance-subject-title">${s.subject}</div>
              <div class="attendance-subject-code">${s.code}</div>
            </div>
            <span class="podium-badge-pill ${riskBadgeClass}">${riskLabel}</span>
          </div>
          <div class="attendance-percentage" style="color: ${fillClass};">${s.attendance}%</div>
          <div class="attendance-progress-bar">
            <div class="attendance-progress-fill" style="width: ${s.attendance}%; background: ${fillClass};"></div>
          </div>
          <div style="font-size: 0.74rem; color: var(--text-muted); display: flex; justify-content: space-between;">
            <span>Attended: ${s.attended || Math.round(s.attendance * 0.5)} / 50</span>
            <span>Mandatory: 75%</span>
          </div>
        </div>
      `;
    }).join("");
  }

  // Render Detailed Attendance Table
  const records = state.attendanceData.cohort_attendance || [];
  if (tbody) {
    const filtered = records.filter(r => {
      if (riskFilter === "All") return true;
      if (riskFilter === "High") return r.attendance_overall < 50;
      if (riskFilter === "Medium") return r.attendance_overall >= 50 && r.attendance_overall < 60;
      if (riskFilter === "Low") return r.attendance_overall >= 60 && r.attendance_overall < 75;
      if (riskFilter === "Safe") return r.attendance_overall >= 75;
      return true;
    });

    tbody.innerHTML = filtered.map(r => {
      let riskBadge = `<span class="podium-badge-pill badge-risk-safe">Safe (&ge;75%)</span>`;
      if (r.attendance_overall < 50) riskBadge = `<span class="podium-badge-pill badge-risk-high">High Risk (&lt;50%)</span>`;
      else if (r.attendance_overall < 60) riskBadge = `<span class="podium-badge-pill badge-risk-med">Medium Risk (50-59%)</span>`;
      else if (r.attendance_overall < 75) riskBadge = `<span class="podium-badge-pill badge-risk-low">Low Risk (60-74%)</span>`;

      return `
        <tr>
          <td><strong>${r.student_name}</strong></td>
          <td><code>${r.roll_no}</code></td>
          <td><strong>${r.attendance_overall}%</strong></td>
          <td>${r.attendance_recent_30d}%</td>
          <td>${riskBadge}</td>
          <td>${r.consecutive_absences || 0} Days</td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="dispatchAttendanceAlert('${r.student_id}', 'Statutory Attendance')">
              <span>Notify Mentor</span>
            </button>
          </td>
        </tr>
      `;
    }).join("");
  }
}

async function dispatchAttendanceAlert(studentId, subject) {
  showGlobalLoader(400);
  try {
    const res = await fetch(`${API_BASE}/attendance/alert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: studentId, subject: subject, note: "Automated alert: Student attendance is below university statutory threshold." })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Threshold alert dispatched to Mentor for student ${studentId}.`, "success", "Alert Dispatched");
    } else {
      showToast(data.error || "Failed to dispatch alert.", "error");
    }
  } catch (err) {
    showToast("Error dispatching attendance alert.", "error");
  }
}

// ==========================================================================
// MODULE D: TASK, ASSIGNMENT & PROJECT MANAGEMENT WITH AI CHECK
// ==========================================================================

async function fetchTasks() {
  try {
    const res = await fetch(`${API_BASE}/tasks`);
    const data = await res.json();
    state.tasks = data.tasks || [];
    renderTasksView();
  } catch (err) {
    console.error("Error fetching tasks:", err);
  }
}

function renderTasksView() {
  const container = document.getElementById("tasks-list-container");
  const roleBtnContainer = document.getElementById("task-view-role-btn");
  const taskSelect = document.getElementById("upload-selected-task");
  if (!container) return;

  const isFaculty = state.currentUser.role === "Faculty" || state.currentUser.role === "Mentor";

  // Faculty create task button
  if (roleBtnContainer) {
    roleBtnContainer.innerHTML = isFaculty ? `
      <button class="btn btn-primary" onclick="toggleTaskCreatePanel(true)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        <span>Publish New Task</span>
      </button>
    ` : "";
  }

  // Populate upload dropdown
  if (taskSelect) {
    taskSelect.innerHTML = state.tasks.map(t => `<option value="${t.id}">${t.title} (${t.type})</option>`).join("");
    onSelectTaskForUpload();
  }

  // Render tasks list
  container.innerHTML = state.tasks.map(t => {
    const typeBadge = t.type === "Project" 
      ? `<span class="task-type-badge badge-project">Project (Video, Doc, Photo)</span>`
      : `<span class="task-type-badge badge-assignment">Assignment (Doc, Photo Only)</span>`;

    let submissionsHtml = "";
    const mySubmissions = (t.submissions || []).filter(sub => isFaculty || (state.currentUser && sub.student_id === state.currentUser.student_id));
    if (mySubmissions.length > 0) {
      submissionsHtml = `
        <div style="margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border-light);">
          <div style="font-size: 0.76rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px;">
            ${isFaculty ? `Student Submissions (${mySubmissions.length}):` : 'My Submission & Verification Status:'}
          </div>
          ${mySubmissions.map(sub => `
            <div style="background: var(--bg-inset); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 12px; margin-bottom: 8px;">
              <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div>
                  <strong style="font-size: 0.85rem;">${sub.student_name}</strong>
                  <span style="font-size: 0.74rem; color: var(--text-muted); margin-left: 6px;">${sub.file_name} (${sub.file_size_mb} MB)</span>
                </div>
                <div style="display: flex; gap: 6px;">
                  ${isFaculty ? `
                    <button class="btn btn-outline-primary btn-sm" id="btn-ai-scan-${sub.id}" onclick="runManualAICheck('${sub.id}')">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                      <span>Run AI &amp; Copy Verification</span>
                    </button>
                  ` : `
                    <button class="btn btn-secondary btn-sm" onclick="openAppealModal('${sub.id}', '${t.title}')">
                      <span>Request Human Appeal</span>
                    </button>
                  `}
                </div>
              </div>
              <div id="ai-results-${sub.id}">
                ${sub.ai_checked || sub.stage1_similarity_score !== undefined ? renderAIScanResults(sub, sub.id, t.title) : ''}
              </div>
            </div>
          `).join("")}
        </div>
      `;
    }

    const criteriaSnippet = t.marking_criteria ? `
      <div style="margin-top: 8px; padding: 6px 10px; background: var(--bg-sand); border-radius: var(--radius-xs); font-size: 0.74rem; color: var(--text-muted);">
        <strong>Rubric:</strong> ${t.marking_criteria} ${t.required_word_count ? `&bull; Word Count: ${t.required_word_count}` : ''}
      </div>
    ` : '';

    return `
      <div class="task-card">
        <div class="task-card-header">
          <div>
            <div style="font-size: 0.76rem; color: var(--text-muted); text-transform: uppercase; font-weight: 700;">${t.course}</div>
            <h4 style="font-size: 1.05rem; margin-top: 2px;">${t.title}</h4>
          </div>
          ${typeBadge}
        </div>
        <p style="font-size: 0.84rem; color: var(--text-muted); line-height: 1.5; margin-bottom: 8px;">${t.description}</p>
        ${criteriaSnippet}
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.76rem; color: var(--text-subtle); margin-top: 10px;">
          <span>Due: <strong>${t.due_date}</strong></span>
          <span>Max Size: <strong>80 MB</strong></span>
        </div>
        ${submissionsHtml}
      </div>
    `;
  }).join("");
}

function toggleTaskCreatePanel(show) {
  const panel = document.getElementById("faculty-task-create-panel");
  if (panel) panel.style.display = show ? "block" : "none";
}

async function submitCreateTask() {
  const title = document.getElementById("task-input-title").value.trim();
  const course = document.getElementById("task-input-course").value;
  const type = document.getElementById("task-input-type").value;
  const dueDate = document.getElementById("task-input-due").value;
  const desc = document.getElementById("task-input-desc").value.trim();
  const criteria = (document.getElementById("task-input-criteria") ? document.getElementById("task-input-criteria").value : "").trim();
  const wordCount = parseInt(document.getElementById("task-input-word-count") ? document.getElementById("task-input-word-count").value : "500", 10) || 500;
  const paragraphCount = parseInt(document.getElementById("task-input-paragraph-count") ? document.getElementById("task-input-paragraph-count").value : "4", 10) || 4;
  const formatAllowed = (document.getElementById("task-input-format") ? document.getElementById("task-input-format").value : "PDF, DOCX, Images").trim();
  const points = (document.getElementById("task-input-points") ? document.getElementById("task-input-points").value : "").trim();
  const resources = (document.getElementById("task-input-resources") ? document.getElementById("task-input-resources").value : "").trim();

  if (!title || !desc) {
    showToast("Please provide task title and description.", "warning");
    return;
  }

  showGlobalLoader(500);
  try {
    const res = await fetch(`${API_BASE}/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title,
        course: course,
        type: type,
        due_date: dueDate,
        description: desc,
        marking_criteria: criteria,
        required_word_count: wordCount,
        paragraph_count: paragraphCount,
        submission_format: formatAllowed,
        required_points: points,
        attached_resources: resources
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Task '${title}' published successfully!`, "success", "Task Created");
      toggleTaskCreatePanel(false);
      await fetchTasks();
    } else {
      showToast(data.error || "Failed to create task.", "error");
    }
  } catch (err) {
    showToast("Error creating task.", "error");
  }
}

function onSelectTaskForUpload() {
  const select = document.getElementById("upload-selected-task");
  const limitsLabel = document.getElementById("dropzone-type-limits");
  if (!select || !limitsLabel) return;

  const taskId = select.value;
  const task = state.tasks.find(t => t.id === taskId);
  if (task && task.type === "Assignment") {
    limitsLabel.textContent = "Assignment: PDF, DOCX, Photo ONLY. Video files are strictly blocked. (Max 80 MB)";
  } else {
    limitsLabel.textContent = "Project: Video (MP4/MOV), PDF, DOCX, Photo accepted. (Max 80 MB)";
  }
}

function triggerFileUpload() {
  const input = document.getElementById("task-file-input");
  if (input) input.click();
}

function handleFileSelection(e) {
  const file = e.target.files[0];
  if (!file) return;

  const select = document.getElementById("upload-selected-task");
  const taskId = select ? select.value : null;
  const task = state.tasks.find(t => t.id === taskId);

  // Strict 80 MB Size Check
  const maxBytes = 80 * 1024 * 1024;
  if (file.size > maxBytes) {
    showToast(`File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds 80 MB limit.`, "error", "Upload Blocked");
    e.target.value = "";
    return;
  }

  // Strict Assignment vs Project Type Validation
  const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
  const isVideo = [".mp4", ".mov", ".m4v"].includes(ext);

  if (task && task.type === "Assignment" && isVideo) {
    showToast("Assignments strictly accept Photos and Documents only. Video files are blocked.", "error", "Validation Failed");
    e.target.value = "";
    return;
  }

  state.selectedUploadFile = file;

  const preview = document.getElementById("upload-file-preview");
  const fnEl = document.getElementById("upload-filename");
  const fsEl = document.getElementById("upload-filesize");

  if (preview) preview.style.display = "block";
  if (fnEl) fnEl.textContent = file.name;
  if (fsEl) fsEl.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB / 80 MB`;
}

function clearSelectedFile() {
  state.selectedUploadFile = null;
  const preview = document.getElementById("upload-file-preview");
  const input = document.getElementById("task-file-input");
  if (preview) preview.style.display = "none";
  if (input) input.value = "";
}

async function submitTaskFile() {
  if (!state.selectedUploadFile) {
    showToast("Please choose a file to upload first.", "warning");
    return;
  }

  const select = document.getElementById("upload-selected-task");
  const taskId = select ? select.value : (state.tasks[0] ? state.tasks[0].id : "TASK-001");
  const videoTurnPath = (document.getElementById("upload-video-turn-input") ? document.getElementById("upload-video-turn-input").value : "").trim();
  const textExcerpt = (document.getElementById("upload-text-excerpt-input") ? document.getElementById("upload-text-excerpt-input").value : "").trim();

  setBtnLoading("btn-submit-task", true, "Uploading...");
  showGlobalLoader(700);

  // Convert file to base64
  const reader = new FileReader();
  reader.onload = async function() {
    const base64Data = reader.result.split(",")[1];
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_name: state.selectedUploadFile.name,
          file_data_base64: base64Data,
          video_turn_path: videoTurnPath,
          text_excerpt: textExcerpt
        })
      });
      const data = await res.json();
      if (data.success) {
        showToast("Submission uploaded with 3-stage verification metadata! (Manual AI scan will be run by instructor)", "success", "Submitted");
        clearSelectedFile();
        if (document.getElementById("upload-video-turn-input")) document.getElementById("upload-video-turn-input").value = "";
        if (document.getElementById("upload-text-excerpt-input")) document.getElementById("upload-text-excerpt-input").value = "";
        await fetchTasks();
      } else {
        showToast(data.error || "Upload failed.", "error");
      }
    } catch (err) {
      showToast("Error uploading submission.", "error");
    } finally {
      setBtnLoading("btn-submit-task", false);
    }
  };
  reader.readAsDataURL(state.selectedUploadFile);
}

// TEACHER-ONLY MANUAL AI ORIGINALITY SCAN
async function runManualAICheck(submissionId) {
  setBtnLoading(`btn-ai-scan-${submissionId}`, true, "Scanning...");
  showGlobalLoader(600);

  try {
    const res = await fetch(`${API_BASE}/submissions/${submissionId}/ai-check`, {
      method: "POST"
    });
    const data = await res.json();
    if (data.success) {
      showToast("AI & 3-Stage Copy Verification complete.", "success", "Scan Finished");
      const targetDiv = document.getElementById(`ai-results-${submissionId}`);
      if (targetDiv) {
        targetDiv.innerHTML = renderAIScanResults(data.scan_results, submissionId);
      }
    } else {
      showToast(data.error || "AI Scan failed.", "error");
    }
  } catch (err) {
    showToast("Error running AI verification.", "error");
  } finally {
    setBtnLoading(`btn-ai-scan-${submissionId}`, false);
  }
}

function renderAIScanResults(scan, subId = "", taskTitle = "Coursework") {
  const human = scan.human_score !== undefined ? scan.human_score : 72;
  const ai = scan.ai_score !== undefined ? scan.ai_score : 18;
  const copy = scan.copy_score !== undefined ? scan.copy_score : 10;
  const s1Sim = scan.stage1_similarity_score !== undefined ? scan.stage1_similarity_score : 14.5;
  const s2Status = scan.stage2_video_status || "Verified (Notebook Continuous)";
  const s3Integrity = scan.stage3_video_integrity_score !== undefined ? scan.stage3_video_integrity_score : 98.2;
  const flagged = scan.flagged_passages || [
    "Analysis of cache coherence protocols in multi-core distributed nodes shows 94% similarity to Wikipedia entry.",
    "Section 2.4 derivation contains typical repetitive syntactical markers consistent with generative LLM output."
  ];

  return `
    <div class="ai-verify-panel" style="margin-top: 10px;">
      <div class="ai-verify-header">
        <h5>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          <span>3-Stage Integrity &amp; Verification Report</span>
        </h5>
        <span style="font-size: 0.72rem; color: var(--text-muted);">Verified at: ${scan.timestamp || new Date().toLocaleTimeString()}</span>
      </div>

      <!-- 3-Stage Result Grid -->
      <div class="stage-result-grid" style="margin-bottom: 12px;">
        <div class="stage-card">
          <div style="font-size: 0.7rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase;">Stage 1: Text Similarity</div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
            <strong style="font-size: 0.95rem; color: var(--primary);">${s1Sim}% Similarity</strong>
            <span class="${s1Sim < 25 ? 'stage-badge-ok' : 'stage-badge-review'}">${s1Sim < 25 ? 'Acceptable' : 'Review'}</span>
          </div>
        </div>

        <div class="stage-card">
          <div style="font-size: 0.7rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase;">Stage 2: Page-Turn Video</div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
            <strong style="font-size: 0.8rem; color: var(--text-main);">${s2Status}</strong>
            <span class="stage-badge-ok">Verified</span>
          </div>
        </div>

        <div class="stage-card">
          <div style="font-size: 0.7rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase;">Stage 3: Video Integrity</div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
            <strong style="font-size: 0.95rem; color: var(--risk-safe);">${s3Integrity}% Clean</strong>
            <span class="stage-badge-ok">No Cuts</span>
          </div>
        </div>
      </div>

      <div class="ai-score-bars">
        <div class="ai-score-bar-human" style="width: ${human}%;"></div>
        <div class="ai-score-bar-ai" style="width: ${ai}%;"></div>
        <div class="ai-score-bar-copy" style="width: ${copy}%;"></div>
      </div>

      <div class="ai-legend">
        <span><span class="ai-legend-dot" style="background: var(--primary);"></span> Human: <strong>${human}%</strong></span>
        <span><span class="ai-legend-dot" style="background: var(--accent-terracotta);"></span> AI Generated: <strong>${ai}%</strong></span>
        <span><span class="ai-legend-dot" style="background: var(--risk-high);"></span> Direct Copy: <strong>${copy}%</strong></span>
      </div>

      <div style="font-size: 0.76rem; font-weight: 700; color: var(--text-muted); margin: 8px 0 4px 0;">Flagged Snippets:</div>
      ${flagged.map(f => `<div class="flagged-snippet">${f}</div>`).join("")}

      <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <span style="font-size: 0.7rem; color: var(--text-muted);">Assists human review; never used for automated sanctions.</span>
        <div style="display: flex; gap: 6px;">
          ${subId ? `
            <button class="btn btn-secondary btn-sm" onclick="openAppealModal('${subId}', '${taskTitle || 'Coursework'}')">
              <span>Request Human Appeal</span>
            </button>
          ` : ''}
          <button class="btn btn-terracotta btn-sm" onclick="notifyAIFlag('${scan.submission_id || subId || ''}')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
            <span>Notify Flag</span>
          </button>
        </div>
      </div>
    </div>
  `;
}

async function notifyAIFlag(subId) {
  showGlobalLoader(300);
  try {
    const res = await fetch(`${API_BASE}/submissions/${subId || 'SUB-001'}/notify-flag`, {
      method: "POST"
    });
    const data = await res.json();
    if (data.success) {
      showToast("Mentor and student notified of integrity check flag.", "info", "Flag Notified");
    } else {
      showToast(data.error || "Failed to notify.", "error");
    }
  } catch (err) {
    showToast("Error notifying flag.", "error");
  }
}

// ==========================================================================
// MODULE E: ACADEMIC RESOURCE HUB & QUESTION-DRIVEN AI SUMMARIZER
// ==========================================================================

async function fetchAcademicResources() {
  try {
    const res = await fetch(`${API_BASE}/academic-hub/resources`);
    const data = await res.json();
    state.resources = data.resources || [];
    renderAcademicHubView();
  } catch (err) {
    console.error("Error fetching academic resources:", err);
  }
}

function switchHubSubject(subj) {
  state.activeHubSubject = subj;
  document.querySelectorAll(".hub-subject-tab").forEach(tab => {
    tab.classList.toggle("active", tab.textContent.includes(subj) || (subj === "All" && tab.textContent.includes("All")));
  });
  renderAcademicHubView();
}

function renderAcademicHubView() {
  const grid = document.getElementById("academic-resources-grid");
  const typeFilter = document.getElementById("hub-type-filter") ? document.getElementById("hub-type-filter").value : "All";
  const yearFilter = document.getElementById("hub-pyq-year-filter") ? document.getElementById("hub-pyq-year-filter").value : "All";
  if (!grid) return;

  const facultyActions = document.getElementById("hub-faculty-actions");
  if (facultyActions) {
    const isInstitutional = state.currentUser && state.currentUser.role !== "Student";
    facultyActions.classList.toggle("hidden", !isInstitutional);
  }

  const filtered = state.resources.filter(r => {
    if (state.activeHubSubject !== "All" && r.subject !== state.activeHubSubject) return false;
    const cat = r.category || r.type;
    if (typeFilter !== "All" && cat !== typeFilter) return false;
    const yr = (r.year || r.pyq_year)?.toString();
    if (yearFilter !== "All" && yr !== yearFilter) return false;
    return true;
  });

  if (filtered.length === 0) {
    grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 24px; color: var(--text-muted);">No resources found matching the selected filters.</div>`;
    return;
  }

  grid.innerHTML = filtered.map(r => `
    <div class="resource-card">
      <div>
        <div class="resource-card-header">
          <div class="resource-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <div style="flex: 1;">
            <div class="resource-title">${r.title}</div>
            <div class="resource-sub">${r.subject} &bull; ${r.semester || 'Semester 6'}</div>
          </div>
          <span class="badge" style="background: var(--bg-inset); color: var(--text-main); font-size: 0.72rem; border: 1px solid var(--border-color);">${r.category || r.type || 'Lecture Notes'}</span>
        </div>
        <p style="font-size: 0.82rem; color: var(--text-muted); line-height: 1.5; margin-bottom: 12px;">${r.preview_text || r.description || 'Comprehensive verified university course study material and examination references.'}</p>
        <div style="font-size: 0.74rem; color: var(--text-subtle);">
          Format: <strong>${r.file_format || 'PDF'}</strong> &bull; Size: <strong>${r.file_size || r.file_size_mb || '2.4 MB'}</strong>
          ${r.year || r.pyq_year ? `&bull; Term/Year: <strong>${r.year || r.pyq_year}</strong>` : ''}
        </div>
      </div>
      <div class="resource-card-actions">
        <a class="btn btn-secondary btn-sm" href="#" onclick="event.preventDefault(); showToast('Downloading ${r.title}...', 'info');">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          <span>Download</span>
        </a>
        <button class="btn btn-secondary btn-sm" onclick="openPyqSolutions('${r.id}')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
          <span>Model Solutions</span>
        </button>
        <button class="btn btn-outline-primary btn-sm" onclick="populateSummarizerPrompt('${r.id}', '${r.title}')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
          <span>Ask AI</span>
        </button>
      </div>
    </div>
  `).join("");
}

function setQuickPrompt(text) {
  const input = document.getElementById("ai-summarize-question");
  if (input) {
    input.value = text;
    input.focus();
    submitNoteSummarizePrompt();
  }
}

function openUploadResourceModal() {
  openModal("upload-resource-modal");
}

async function submitAcademicResourceUpload() {
  const title = document.getElementById("res-title-input")?.value?.trim();
  const subject = document.getElementById("res-subject-select")?.value;
  const category = document.getElementById("res-category-select")?.value;
  const semester = document.getElementById("res-semester-select")?.value;
  const year = parseInt(document.getElementById("res-year-input")?.value || "2026", 10);
  const contentText = document.getElementById("res-content-input")?.value?.trim() || "";

  if (!title) {
    showToast("Please provide a resource title.", "warning");
    return;
  }

  showGlobalLoader(500);
  try {
    const res = await authenticatedFetch(`${API_BASE}/academic-hub/resources`, {
      method: "POST",
      body: JSON.stringify({
        title: title,
        subject: subject,
        category: category,
        semester: semester,
        year: year,
        exam_term: "Mid-Term / Continuous",
        file_name: `${title.toLowerCase().replace(/[^a-z0-9]/g, "_")}.pdf`,
        file_size: "2.4 MB",
        content_text: contentText
      })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message || "Resource published successfully!", "success", "Published");
      closeModal("upload-resource-modal");
      const titleInput = document.getElementById("res-title-input");
      const contentInput = document.getElementById("res-content-input");
      if (titleInput) titleInput.value = "";
      if (contentInput) contentInput.value = "";
      fetchAcademicResources();
    } else {
      showToast(data.error || "Failed to publish resource.", "error");
    }
  } catch (err) {
    showToast("Error connecting to server.", "error");
  }
}

async function openPyqSolutions(resourceId) {
  showGlobalLoader(400);
  try {
    const res = await authenticatedFetch(`${API_BASE}/academic-hub/resources/${resourceId}/solutions`);
    const data = await res.json();
    if (res.ok && data.success && data.resource) {
      const r = data.resource;
      state.currentModalResource = r;
      const titleEl = document.getElementById("pyq-solution-title");
      const metaEl = document.getElementById("pyq-solution-meta");
      const bodyEl = document.getElementById("pyq-solution-body");

      if (titleEl) titleEl.textContent = r.title;
      if (metaEl) metaEl.innerHTML = `<strong>${r.subject}</strong> &bull; ${r.category} (${r.year || 2026})`;
      if (bodyEl) {
        bodyEl.innerHTML = `
          <div style="margin-bottom: 14px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <span class="rubric-score-badge">Official NEP 2020 Model Marking Rubric</span>
            <span style="font-size: 0.78rem; color: var(--text-muted);">Verified by Department Examination Committee</span>
          </div>
        `;
        const pre = document.createElement("div");
        pre.className = "solution-box";
        pre.textContent = r.content_text;
        bodyEl.appendChild(pre);
      }
      openModal("pyq-solution-modal");
    } else {
      showToast(data.error || "Unable to load model solutions.", "error");
    }
  } catch (err) {
    showToast("Error retrieving solutions.", "error");
  }
}

function summarizeCurrentModalResource() {
  if (state.currentModalResource) {
    closeModal("pyq-solution-modal");
    populateSummarizerPrompt(state.currentModalResource.id, state.currentModalResource.title);
    submitNoteSummarizePrompt();
  }
}

function copyModalContent() {
  if (state.currentModalResource?.content_text) {
    navigator.clipboard.writeText(state.currentModalResource.content_text);
    showToast("Model answers copied to clipboard!", "success", "Copied");
  }
}

function populateSummarizerPrompt(resourceId, resourceTitle) {
  const input = document.getElementById("ai-summarize-question");
  if (input) {
    input.value = `Summarize key derivations and 10-mark exam questions from: ${resourceTitle}`;
    input.focus();
    input.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

async function submitNoteSummarizePrompt() {
  const input = document.getElementById("ai-summarize-question");
  const question = input ? input.value.trim() : "";
  const resultArea = document.getElementById("ai-summarize-result");

  if (!question) {
    showToast("Please enter a question or topic prompt.", "warning");
    return;
  }

  showGlobalLoader(600);
  try {
    const res = await authenticatedFetch(`${API_BASE}/academic-hub/summarize`, {
      method: "POST",
      body: JSON.stringify({ question: question, note_id: "NOTE-201" })
    });
    const data = await res.json();
    if (data.success && resultArea) {
      resultArea.classList.add("active");
      resultArea.innerHTML = `
        <div style="font-weight: 700; color: var(--primary); margin-bottom: 8px; font-size: 0.92rem;">
          AI Study Summary Response:
        </div>
        <div style="white-space: pre-line;">${data.summary}</div>
      `;
      showToast("Study summary generated!", "success", "Summary Ready");
    } else {
      showToast(data.error || "Failed to generate summary.", "error");
    }
  } catch (err) {
    showToast("Error contacting AI Note Summarizer.", "error");
  }
}

// ==========================================================================
// MODULE B: AUTOMATED MENTOR PULSE & WEEKLY REVIEW SCHEDULER
// ==========================================================================

async function fetchMentorPulse() {
  try {
    const res = await fetch(`${API_BASE}/mentor/pulse`);
    const data = await res.json();
    state.pulseFeed = data.pulse_feed || [];
    state.pulseSchedule = data.schedule_status || {};
    renderMentorPulseView();
  } catch (err) {
    console.error("Error fetching mentor pulse:", err);
  }
}

async function fetchMentorReviewSchedule() {
  try {
    const res = await fetch(`${API_BASE}/mentor/review-schedule`);
    const data = await res.json();
    if (data.review_day) {
      state.reviewScheduleDay = data.review_day;
      const select = document.getElementById("mentor-review-day-select");
      if (select) select.value = data.review_day;
    }
  } catch (err) {
    console.error("Error fetching review schedule:", err);
  }
}

function renderMentorPulseView() {
  const container = document.getElementById("mentor-pulse-feed-list");
  const nextSyncEl = document.getElementById("pulse-next-sync-time");
  if (!container) return;

  if (nextSyncEl && state.pulseSchedule) {
    nextSyncEl.innerHTML = `Next Scheduled Sync: <strong>${state.pulseSchedule.next_sync || 'Wednesday, 09:00 AM IST'}</strong>`;
  }

  container.innerHTML = state.pulseFeed.map(item => `
    <div class="pulse-feed-item">
      <div class="pulse-date-stamp">
        <div class="pulse-day-name">${item.day_name || 'MON'}</div>
        <div class="pulse-day-num">${item.day_num || '12'}</div>
      </div>
      <div class="pulse-feed-body">
        <h5>${item.student_name} - ${item.event_title}</h5>
        <p>${item.description}</p>
        <div style="font-size: 0.72rem; color: var(--text-subtle); margin-top: 6px;">
          Cadence: Alternate-Day Automated Sync &bull; ${item.timestamp || 'Today'}
        </div>
      </div>
    </div>
  `).join("");
}

async function saveMentorReviewSchedule() {
  const select = document.getElementById("mentor-review-day-select");
  const chosenDay = select ? select.value : "Friday";

  showGlobalLoader(400);
  try {
    const res = await fetch(`${API_BASE}/mentor/review-schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_day: chosenDay })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Weekly review digest schedule updated to every ${chosenDay}.`, "success", "Schedule Locked");
    } else {
      showToast(data.error || "Failed to update review schedule.", "error");
    }
  } catch (err) {
    showToast("Error updating review schedule.", "error");
  }
}

// ==========================================================================
// MODULE C: BI-WEEKLY PARENT PORTAL / 14-DAY DIGEST
// ==========================================================================

async function fetchParentDigest() {
  try {
    const studentId = state.currentUser.student_id || "STU-101";
    const res = await fetch(`${API_BASE}/parent-digest/${studentId}`);
    state.parentDigest = await res.json();
    renderParentPortalView();
  } catch (err) {
    console.error("Error fetching parent digest:", err);
  }
}

function renderParentPortalView() {
  const container = document.getElementById("parent-portal-content");
  if (!container || !state.parentDigest) return;

  const d = state.parentDigest;
  const extra = d.extracurriculars || [
    { title: "Robotics Club Lead", category: "Leadership", note: "Organized Autonomous Rover Workshop for first-year engineers." },
    { title: "Smart India Hackathon 2026", category: "Hackathon", note: "Finalist in AI in Education track with Team CyberEagles." },
    { title: "Inter-Collegiate Table Tennis", category: "Sports", note: "Won Silver medal in zonal university tournaments." },
    { title: "Rotaract Community Volunteer", category: "Social Impact", note: "Conducted basic coding literacy camps in rural schools." }
  ];

  container.innerHTML = `
    <div class="parent-digest-meta">
      <div>
        <h3>14-Day Holistic Academic &amp; Extracurricular Digest</h3>
        <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 2px;">
          Student Scholar: <strong>${d.student_name}</strong> (Roll: ${d.roll_no}) &bull; Reporting Window: <strong>Past 14 Days</strong>
        </p>
      </div>
      <span class="podium-badge-pill badge-risk-safe">Compliant Status</span>
    </div>

    <!-- 360 Metrics Summary -->
    <div class="parent-metrics-summary">
      <div class="metric-pill-box">
        <div class="label">Attendance (14d)</div>
        <div class="value" style="color: var(--primary);">${d.attendance_percentage || 82}%</div>
      </div>
      <div class="metric-pill-box">
        <div class="label">Academic CGPA</div>
        <div class="value">${d.cgpa || '8.4'}</div>
      </div>
      <div class="metric-pill-box">
        <div class="label">Task Completion</div>
        <div class="value" style="color: var(--primary);">${d.task_completion_rate || '95%'}</div>
      </div>
      <div class="metric-pill-box">
        <div class="label">Conduct / Integrity</div>
        <div class="value" style="color: var(--risk-safe);">Exemplary</div>
      </div>
    </div>

    <!-- Extracurricular Section -->
    <div class="extracurricular-container">
      <h4>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        <span>Extracurricular Activities &amp; Holistic Development</span>
      </h4>
      <div class="extracurricular-grid">
        ${extra.map(e => `
          <div class="extracurricular-item">
            <div class="extracurricular-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            </div>
            <div>
              <div class="extracurricular-title">${e.title}</div>
              <div class="extracurricular-sub">${e.category}: ${e.note}</div>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function openParentReportPreviewModal() {
  const modalBody = document.getElementById("parent-preview-modal-body");
  if (modalBody && state.parentDigest) {
    const d = state.parentDigest;
    modalBody.innerHTML = `
      <div style="border-bottom: 2px solid var(--primary); padding-bottom: 12px; margin-bottom: 16px;">
        <h4 style="color: var(--primary);">EduEagle University Bi-Weekly Parent Dossier</h4>
        <div style="font-size: 0.8rem; color: var(--text-muted);">Confidential Academic &amp; Extracurricular Progress Report</div>
      </div>
      <p><strong>Student:</strong> ${d.student_name} (${d.roll_no})</p>
      <p><strong>Overall Attendance:</strong> ${d.attendance_percentage || 82}%</p>
      <p><strong>Coursework Completion:</strong> ${d.task_completion_rate || '95%'}</p>
      <p><strong>Extracurricular Highlights:</strong> Robotics Club Lead, Hackathon Finalist, Sports Silver Medalist.</p>
      <div style="margin-top: 14px; font-size: 0.76rem; color: var(--text-subtle);">
        Delivered under DPDP Act 2023 parent transparency guidelines.
      </div>
    `;
  }
  openModal("parent-preview-modal");
}

async function sendBiWeeklyDigest() {
  const studentId = state.currentUser.student_id || "STU-101";
  showGlobalLoader(500);
  try {
    const res = await fetch(`${API_BASE}/parent-digest/${studentId}/send`, {
      method: "POST"
    });
    const data = await res.json();
    if (data.success) {
      showToast("Bi-Weekly Parent Digest dispatched via WhatsApp and Email!", "success", "Dispatched to Parents");
    } else {
      showToast(data.error || "Failed to dispatch digest.", "error");
    }
  } catch (err) {
    showToast("Error sending digest.", "error");
  }
}

// ==========================================================================
// COMPATIBILITY & SIMULATOR HELPERS
// ==========================================================================

async function fetchCohortAnalytics() {
  try {
    const res = await fetch(`${API_BASE}/analytics/cohort`);
    state.cohortStats = await res.json();
    renderCohortView();
  } catch (err) {
    console.error("Error fetching cohort stats:", err);
  }
}

function renderCohortView() {
  const kpiGrid = document.getElementById("cohort-kpis");
  const deptTbody = document.getElementById("cohort-dept-table-body");
  if (kpiGrid) {
    kpiGrid.innerHTML = `
      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Active Enrolled Cohort</div>
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          </div>
        </div>
        <div class="kpi-value">1,248</div>
        <div class="kpi-subtext">Students across 4 B.Tech engineering disciplines</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Statutory Attendance Health</div>
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><path d="m9 16 2 2 4-4"/></svg>
          </div>
        </div>
        <div class="kpi-value" style="color: var(--primary);">86.4%</div>
        <div class="kpi-subtext">University average meeting NEP 2020 75% target</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">High Risk Interventions</div>
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
        </div>
        <div class="kpi-value" style="color: var(--risk-high);">14</div>
        <div class="kpi-subtext">Cases assigned to faculty mentors for support</div>
      </div>
    `;
  }

  if (deptTbody) {
    deptTbody.innerHTML = `
      <tr>
        <td><strong>Computer Science &amp; Engineering</strong></td>
        <td>420</td>
        <td><span class="podium-badge-pill badge-risk-safe">12.4 (Low Risk)</span></td>
        <td><button class="btn btn-secondary btn-sm" onclick="switchTab('podium')">View Department</button></td>
      </tr>
      <tr>
        <td><strong>Electronics &amp; Communication</strong></td>
        <td>310</td>
        <td><span class="podium-badge-pill badge-risk-low">18.6 (Low Risk)</span></td>
        <td><button class="btn btn-secondary btn-sm" onclick="switchTab('attendance')">View Department</button></td>
      </tr>
      <tr>
        <td><strong>Mechanical Engineering</strong></td>
        <td>280</td>
        <td><span class="podium-badge-pill badge-risk-med">24.2 (Medium Risk)</span></td>
        <td><button class="btn btn-secondary btn-sm" onclick="switchTab('attendance')">View Department</button></td>
      </tr>
    `;
  }
}

async function runScenario(scenarioKey) {
  showGlobalLoader(500);
  try {
    const res = await fetch(`${API_BASE}/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: scenarioKey, student_id: "STU-101" })
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message || `Scenario ${scenarioKey} simulated.`, "info", "Simulation Active");
      await loadInitialData();
    }
  } catch (err) {
    showToast("Simulation error.", "error");
  }
}

async function resetDemoData() {
  showGlobalLoader(600);
  try {
    const res = await fetch(`${API_BASE}/reset`, { method: "POST" });
    const data = await res.json();
    if (data.success) {
      showToast("Data store restored to pristine state.", "success", "Reset Complete");
      await loadInitialData();
    }
  } catch (err) {
    showToast("Reset error.", "error");
  }
}

// ==========================================================================
// AUTHENTICATION HEADERS HELPER
// ==========================================================================

function getAuthHeaders(extra = {}) {
  const headers = { ...extra };
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  } else if (state.currentUser && state.currentUser.id) {
    headers["Authorization"] = `Bearer edueagle-token-${state.currentUser.id}`;
  } else {
    headers["Authorization"] = "Bearer edueagle-token-USR-001";
  }
  return headers;
}

// ==========================================================================
// FEE MANAGEMENT CONTROLLER (STUDENT & INSTITUTIONAL)
// ==========================================================================

async function fetchFeeData() {
  const isStudent = state.currentUser && state.currentUser.role === "Student";
  if (isStudent) {
    await fetchStudentFee();
  } else {
    await fetchCohortFees();
  }
}

// 1. STUDENT FEE PROFILE & LEDGER
async function fetchStudentFee() {
  try {
    const res = await fetch(`${API_BASE}/fees/my`, {
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (data.success && data.fee_account) {
      state.myFeeAccount = data.fee_account;
      renderStudentFeeView();
    }
  } catch (err) {
    console.error("Error fetching student fee ledger:", err);
  }
}

function renderStudentFeeView() {
  const kpiContainer = document.getElementById("student-fee-kpi-container");
  const compContainer = document.getElementById("student-fee-components-container");
  const txnsTbody = document.getElementById("student-fee-txns-tbody");
  const payModalDueDisplay = document.getElementById("pay-modal-due-display");
  const payModalAmountInput = document.getElementById("pay-modal-amount");

  if (!state.myFeeAccount) {
    if (kpiContainer) {
      kpiContainer.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 24px; color: var(--text-muted);">Loading student fee ledger...</div>`;
    }
    return;
  }

  const acc = state.myFeeAccount;

  // Update Pay Modal Elements
  if (payModalDueDisplay) {
    payModalDueDisplay.textContent = `INR ${Number(acc.due_fee).toLocaleString("en-IN")}.00`;
  }
  if (payModalAmountInput) {
    payModalAmountInput.value = acc.due_fee > 0 ? acc.due_fee : 0;
    payModalAmountInput.max = acc.due_fee;
  }

  // 1. Render KPI Grid
  if (kpiContainer) {
    let statusBadgeClass = "badge-risk-safe";
    if (acc.status.includes("Overdue")) statusBadgeClass = "badge-risk-high";
    else if (acc.status.includes("Grace")) statusBadgeClass = "badge-risk-med";

    kpiContainer.innerHTML = `
      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Annual Billed Academic Fee</div>
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          </div>
        </div>
        <div class="kpi-value">INR ${Number(acc.total_fee).toLocaleString("en-IN")}</div>
        <div class="kpi-subtext">Semester 6 B.Tech Computer Science &amp; Engineering</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Total Fee Paid to Date</div>
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
        </div>
        <div class="kpi-value" style="color: var(--primary);">INR ${Number(acc.paid_fee).toLocaleString("en-IN")}</div>
        <div class="kpi-subtext">Verified by University Bursar Office</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Outstanding Due Balance</div>
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
        </div>
        <div class="kpi-value" style="color: ${acc.due_fee > 0 ? 'var(--accent-terracotta)' : 'var(--primary)'};">INR ${Number(acc.due_fee).toLocaleString("en-IN")}</div>
        <div class="kpi-subtext">${acc.due_fee > 0 ? `Payable by statutory deadline: ${acc.due_date}` : 'All semester fees cleared in full'}</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Account Clearance Status</div>
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          </div>
        </div>
        <div style="margin-top: 6px;">
          <span class="podium-badge-pill ${statusBadgeClass}">${acc.status}</span>
        </div>
        <div class="kpi-subtext" style="margin-top: 10px;">Statutory Examination Hall-Ticket: ${acc.due_fee > 0 && acc.status.includes('Overdue') ? 'Pending Clearance' : 'Active / Issued'}</div>
      </div>
    `;
  }

  // 2. Render Fee Components Grid
  if (compContainer) {
    const components = acc.components && acc.components.length > 0 ? acc.components : [
      { name: "Tuition Fee (Semester 6)", billed: 95000, paid: 65000, balance: 30000, status: "Partial", term: "Academic Instruction & Faculty Labs" },
      { name: "Laboratory & Technology Fee", billed: 32000, paid: 20000, balance: 12000, status: "Partial", term: "Computing, Robotics & High-Performance Clusters" },
      { name: "Examination & Assessment Fee", billed: 12000, paid: 12000, balance: 0, status: "Settled", term: "End-Semester Evaluations & NEP Assessment" },
      { name: "Digital Library & IEEE Portals", billed: 8000, paid: 8000, balance: 0, status: "Settled", term: "ACM, IEEE & Elsevier Research Subscriptions" },
      { name: "Campus Amenities & Sports Facilities", billed: 6000, paid: 0, balance: 6000, status: "Due", term: "Health Center, Gymnasium & Athletic Grounds" }
    ];

    compContainer.innerHTML = components.map(c => {
      let badgeClass = "badge-risk-safe";
      if (c.status === "Due") badgeClass = "badge-risk-high";
      else if (c.status === "Partial") badgeClass = "badge-risk-low";

      return `
        <div class="fee-component-card">
          <div class="fee-comp-header">
            <div>
              <div class="fee-comp-name">${c.name}</div>
              <div class="fee-comp-term">${c.term || 'Semester 6 Statutory Schedule'}</div>
            </div>
            <span class="podium-badge-pill ${badgeClass}">${c.status}</span>
          </div>

          <div class="fee-comp-grid">
            <div>
              <div class="fee-metric-lbl">Billed</div>
              <div class="fee-metric-val">INR ${Number(c.billed).toLocaleString("en-IN")}</div>
            </div>
            <div>
              <div class="fee-metric-lbl">Paid</div>
              <div class="fee-metric-val" style="color: var(--primary);">INR ${Number(c.paid).toLocaleString("en-IN")}</div>
            </div>
            <div>
              <div class="fee-metric-lbl">Balance</div>
              <div class="fee-metric-val" style="color: ${c.balance > 0 ? 'var(--accent-terracotta)' : 'var(--text-main)'};">INR ${Number(c.balance).toLocaleString("en-IN")}</div>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  // 3. Render Verified Transaction Ledger
  if (txnsTbody) {
    const txns = acc.transactions || [];
    if (txns.length === 0) {
      txnsTbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 18px;">No transaction records available.</td></tr>`;
    } else {
      txnsTbody.innerHTML = txns.map(t => `
        <tr>
          <td><strong style="color: var(--primary);">${t.receipt_no}</strong></td>
          <td><code style="font-size: 0.76rem; background: var(--bg-secondary); padding: 2px 6px; border-radius: 4px;">${t.transaction_id || 'NEFT-RECON'}</code></td>
          <td style="font-size: 0.8rem; color: var(--text-muted);">${t.created_at || '2026-08-15'}</td>
          <td>${t.payment_method}</td>
          <td><strong>INR ${Number(t.amount).toLocaleString("en-IN")}.00</strong></td>
          <td><span class="podium-badge-pill badge-risk-safe">Settled / Verified</span></td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="printFeeReceipt('${t.receipt_no}')">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              <span>Receipt</span>
            </button>
          </td>
        </tr>
      `).join("");
    }
  }
}

function openStudentPayModal() {
  if (!state.myFeeAccount) return;
  if (state.myFeeAccount.due_fee <= 0) {
    showToast("All academic fees for Semester 6 are settled in full. No outstanding balance due.", "success", "Account Clear");
    return;
  }
  openModal("pay-fee-modal");
}

async function submitStudentFeePayment() {
  const amtInput = document.getElementById("pay-modal-amount");
  const methodSelect = document.getElementById("pay-modal-method");
  const remarksInput = document.getElementById("pay-modal-remarks");

  const amount = amtInput ? parseFloat(amtInput.value) : 0;
  const method = methodSelect ? methodSelect.value : "UPI (Google Pay)";
  const remarks = remarksInput ? remarksInput.value.trim() : "Online fee payment";

  if (!amount || amount <= 0) {
    showToast("Please enter a valid payment amount greater than INR 0.", "warning");
    return;
  }

  const studentId = state.currentUser ? (state.currentUser.student_id || state.currentUser.id || "STU-101") : "STU-101";

  setBtnLoading("btn-submit-fee-payment", true, "Processing...");
  showGlobalLoader(700);

  try {
    const res = await fetch(`${API_BASE}/fees/${studentId}/pay`, {
      method: "POST",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        amount: amount,
        payment_method: method,
        remarks: remarks
      })
    });
    const data = await res.json();
    if (data.success && data.fee_account) {
      state.myFeeAccount = data.fee_account;
      closeModal("pay-fee-modal");
      renderStudentFeeView();
      showToast(`Payment of INR ${amount.toLocaleString("en-IN")} settled successfully! Official receipt generated.`, "success", "Payment Received");
      printFeeReceipt("latest");
    } else {
      showToast(data.error || "Payment transaction could not be processed.", "error");
    }
  } catch (err) {
    showToast("Error processing payment request. Please check connection.", "error");
  } finally {
    setBtnLoading("btn-submit-fee-payment", false);
  }
}

function printFeeReceipt(receiptNo) {
  const modalBody = document.getElementById("fee-receipt-modal-body");
  if (!modalBody) return;

  const acc = state.myFeeAccount || {
    student_name: state.currentUser ? state.currentUser.name : "Aarav Sharma",
    roll_no: "2023-CSE-042",
    department: "Computer Science & Engineering",
    total_fee: 153000,
    paid_fee: 105000,
    due_fee: 48000,
    transactions: []
  };

  let txn = null;
  if (receiptNo && receiptNo !== "latest" && acc.transactions) {
    txn = acc.transactions.find(t => t.receipt_no === receiptNo);
  }
  if (!txn && acc.transactions && acc.transactions.length > 0) {
    txn = acc.transactions[0];
  }
  if (!txn) {
    txn = {
      receipt_no: "TXN-REC-901",
      transaction_id: "HDFC-UPI-8840192",
      created_at: new Date().toISOString().replace("T", " ").substring(0, 19),
      payment_method: "UPI (Google Pay)",
      amount: 45000,
      remarks: "Semester 6 Academic Fee Installment"
    };
  }

  modalBody.innerHTML = `
    <div class="fee-receipt-sheet">
      <div class="receipt-header">
        <div style="display: flex; align-items: center; gap: 12px;">
          <div style="width: 44px; height: 44px; border-radius: 8px; background: var(--bg-secondary); border: 1px solid var(--border-color); display: flex; align-items: center; justify-content: center; color: var(--primary);">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          </div>
          <div>
            <h3 style="margin: 0; font-size: 1.05rem; color: var(--primary);">EduEagle University Office of the Bursar</h3>
            <div style="font-size: 0.75rem; color: var(--text-muted);">Statutory Fee Acknowledgment &bull; NEP 2020 Framework</div>
          </div>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 0.72rem; color: var(--text-muted);">Receipt Number</div>
          <div style="font-weight: 800; font-size: 0.95rem; color: var(--primary);">${txn.receipt_no}</div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px; font-size: 0.82rem;">
        <div>
          <div style="color: var(--text-muted); font-size: 0.74rem;">Student Scholar</div>
          <div style="font-weight: 700;">${acc.student_name} (${acc.roll_no})</div>
          <div style="color: var(--text-muted); font-size: 0.74rem; margin-top: 2px;">Dept: ${acc.department}</div>
        </div>
        <div style="text-align: right;">
          <div style="color: var(--text-muted); font-size: 0.74rem;">Transaction Timestamp</div>
          <div style="font-weight: 700;">${txn.created_at}</div>
          <div style="color: var(--text-muted); font-size: 0.74rem; margin-top: 2px;">Instrument: ${txn.payment_method}</div>
        </div>
      </div>

      <div class="marks-table-wrap" style="margin-bottom: 16px;">
        <table class="marks-table" style="font-size: 0.82rem;">
          <thead>
            <tr>
              <th>Description / Purpose</th>
              <th>Reference ID</th>
              <th style="text-align: right;">Amount Paid</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>${txn.remarks || 'Semester 6 Academic Term Fee Clearance'}</td>
              <td><code>${txn.transaction_id || 'RECON-BANK-ID'}</code></td>
              <td style="text-align: right; font-weight: 800; color: var(--primary);">INR ${Number(txn.amount).toLocaleString("en-IN")}.00</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div style="display: flex; justify-content: space-between; align-items: flex-end; padding-top: 10px; border-top: 1px dashed var(--border-color); font-size: 0.78rem;">
        <div>
          <div style="color: var(--text-muted);">Remaining Semester Due Balance:</div>
          <div style="font-weight: 700; color: ${acc.due_fee > 0 ? 'var(--accent-terracotta)' : 'var(--primary)'};">INR ${Number(acc.due_fee).toLocaleString("en-IN")}.00</div>
        </div>
        <div style="text-align: right;">
          <div class="podium-badge-pill badge-risk-safe" style="display: inline-flex; margin-bottom: 4px;">Verified Electronic Seal</div>
          <div style="font-size: 0.72rem; color: var(--text-muted);">University Bursar Reconciliation Desk</div>
        </div>
      </div>
    </div>
  `;

  openModal("fee-receipt-modal");
}

// 2. INSTITUTIONAL COHORT FEE MANAGEMENT (FACULTY / BURSAR)
async function fetchCohortFees() {
  try {
    const res = await fetch(`${API_BASE}/fees`, {
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (data.success) {
      state.cohortFees = data;
      renderInstitutionalFeeView();
    }
  } catch (err) {
    console.error("Error fetching cohort fees summary:", err);
  }
}

function renderInstitutionalFeeView() {
  const kpiContainer = document.getElementById("institutional-fee-kpi-container");
  const tbody = document.getElementById("cohort-fee-tbody");
  const modalStudentSelect = document.getElementById("record-modal-student");

  if (!state.cohortFees) {
    if (kpiContainer) {
      kpiContainer.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 24px; color: var(--text-muted);">Loading cohort financial intelligence...</div>`;
    }
    return;
  }

  const summary = state.cohortFees.summary || {
    total_invoiced: 1224000,
    total_collected: 890000,
    total_overdue: 334000,
    clearance_rate: 72.7
  };

  // 1. Render Billing KPIs
  if (kpiContainer) {
    kpiContainer.innerHTML = `
      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Total Cohort Invoiced</div>
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          </div>
        </div>
        <div class="kpi-value">INR ${Number(summary.total_invoiced).toLocaleString("en-IN")}</div>
        <div class="kpi-subtext">Cumulative B.Tech academic year statutory billing</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Verified Collections</div>
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
        </div>
        <div class="kpi-value" style="color: var(--primary);">INR ${Number(summary.total_collected).toLocaleString("en-IN")}</div>
        <div class="kpi-subtext">Online gateways, NEFT &amp; bank draft deposits</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Outstanding Cohort Dues</div>
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
        </div>
        <div class="kpi-value" style="color: var(--accent-terracotta);">INR ${Number(summary.total_overdue).toLocaleString("en-IN")}</div>
        <div class="kpi-subtext">Overdue installments subject to advisory follow-up</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Cohort Clearance Rate</div>
          <div class="kpi-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          </div>
        </div>
        <div class="kpi-value" style="color: var(--primary);">${summary.clearance_rate}%</div>
        <div class="kpi-subtext">University statutory financial compliance target: 80%</div>
      </div>
    `;
  }

  // 2. Populate modal student selector
  if (modalStudentSelect && state.cohortFees.students) {
    modalStudentSelect.innerHTML = state.cohortFees.students.map(s => `
      <option value="${s.student_id}">${s.name} (${s.roll_no}) - Due: INR ${Number(s.due_fee).toLocaleString("en-IN")}</option>
    `).join("");
  }

  // 3. Render Student Fee Accounts Ledger Table
  filterCohortFeeLedger();
}

function filterCohortFeeLedger() {
  const tbody = document.getElementById("cohort-fee-tbody");
  const filterSelect = document.getElementById("fee-filter-status");
  if (!tbody || !state.cohortFees || !state.cohortFees.students) return;

  const filter = filterSelect ? filterSelect.value : "All";
  const students = state.cohortFees.students.filter(s => {
    if (filter === "All") return true;
    if (filter === "Overdue") return s.status.includes("Overdue") || s.due_fee > 0;
    if (filter === "Grace Period") return s.status.includes("Grace");
    if (filter === "Clear") return s.due_fee <= 0 || s.status.includes("Paid");
    return true;
  });

  if (students.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 20px;">No student fee accounts matching '${filter}'.</td></tr>`;
    return;
  }

  tbody.innerHTML = students.map(s => {
    let badgeClass = "badge-risk-safe";
    if (s.status.includes("Overdue")) badgeClass = "badge-risk-high";
    else if (s.status.includes("Grace")) badgeClass = "badge-risk-med";

    return `
      <tr>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 28px; height: 28px; border-radius: 6px; background: var(--bg-sand); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.74rem; color: var(--primary);">
              ${s.name.substring(0, 2).toUpperCase()}
            </div>
            <strong>${s.name}</strong>
          </div>
        </td>
        <td><code>${s.roll_no}</code></td>
        <td style="font-size: 0.8rem; color: var(--text-muted);">${s.department}</td>
        <td>INR ${Number(s.total_fee).toLocaleString("en-IN")}</td>
        <td style="color: var(--primary); font-weight: 600;">INR ${Number(s.paid_fee).toLocaleString("en-IN")}</td>
        <td style="color: ${s.due_fee > 0 ? 'var(--accent-terracotta)' : 'var(--text-main)'}; font-weight: 700;">INR ${Number(s.due_fee).toLocaleString("en-IN")}</td>
        <td><span class="podium-badge-pill ${badgeClass}">${s.status}</span></td>
        <td style="font-size: 0.74rem; color: var(--text-muted);">${s.last_reminded ? s.last_reminded.substring(0, 10) : 'Not Reminded'}</td>
        <td>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            ${s.due_fee > 0 ? `
              <button class="btn btn-terracotta btn-sm" onclick="sendFeeReminder('${s.student_id}')">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
                <span>Remind</span>
              </button>
              <button class="btn btn-secondary btn-sm" onclick="openRecordPaymentModalFor('${s.student_id}')">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                <span>Record</span>
              </button>
            ` : ''}
            <button class="btn btn-outline-primary btn-sm" onclick="inspectStudentWorkFromFee('${s.student_id}')">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              <span>Work</span>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function openRecordPaymentModalFor(studentId) {
  openRecordPaymentModal();
  const select = document.getElementById("record-modal-student");
  if (select) {
    select.value = studentId;
  }
}

function openRecordPaymentModal() {
  openModal("record-payment-modal");
}

async function submitRecordPayment() {
  const select = document.getElementById("record-modal-student");
  const amtInput = document.getElementById("record-modal-amount");
  const methodSelect = document.getElementById("record-modal-method");
  const receiptInput = document.getElementById("record-modal-receipt");
  const remarksInput = document.getElementById("record-modal-remarks");

  const studentId = select ? select.value : "STU-101";
  const amount = amtInput ? parseFloat(amtInput.value) : 0;
  const method = methodSelect ? methodSelect.value : "Bank Draft / NEFT";
  const receiptNo = receiptInput ? receiptInput.value.trim() : "";
  const remarks = remarksInput ? remarksInput.value.trim() : "Offline fee deposit";

  if (!amount || amount <= 0) {
    showToast("Please specify a valid payment amount greater than INR 0.", "warning");
    return;
  }

  setBtnLoading("btn-submit-record-payment", true, "Recording...");
  showGlobalLoader(500);

  try {
    const res = await fetch(`${API_BASE}/fees/${studentId}/record-payment`, {
      method: "POST",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        amount: amount,
        payment_method: method,
        receipt_no: receiptNo,
        remarks: remarks
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Institutional fee deposit of INR ${amount.toLocaleString("en-IN")} recorded for ${studentId}.`, "success", "Payment Recorded");
      closeModal("record-payment-modal");
      await fetchCohortFees();
    } else {
      showToast(data.error || "Failed to record payment.", "error");
    }
  } catch (err) {
    showToast("Error communicating with bursar payment service.", "error");
  } finally {
    setBtnLoading("btn-submit-record-payment", false);
  }
}

async function sendFeeReminder(studentId) {
  showGlobalLoader(400);
  try {
    const res = await fetch(`${API_BASE}/fees/${studentId}/remind`, {
      method: "POST",
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        channel: "WhatsApp & Email",
        message: "Notice: Academic fee installment due for Semester 6."
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Statutory fee notice dispatched to ${studentId} via WhatsApp and Email.`, "info", "Reminder Sent");
      await fetchCohortFees();
    } else {
      showToast(data.error || "Failed to dispatch reminder.", "error");
    }
  } catch (err) {
    showToast("Error dispatching fee reminder notice.", "error");
  }
}

// ==========================================================================
// STUDENT 360 & COMPLETE WORK INSPECTION (FULL AUTHORITY)
// ==========================================================================

async function fetchStudentsPortfolio() {
  const selector = document.getElementById("portfolio-student-selector");
  if (!selector) return;

  const defaultStudents = [
    { id: "STU-101", name: "Aarav Sharma", roll: "2023-CSE-042", dept: "Computer Science" },
    { id: "STU-102", name: "Diya Patel", roll: "2023-CSE-018", dept: "Computer Science" },
    { id: "STU-103", name: "Rohan Iyer", roll: "2023-CSE-089", dept: "Computer Science" },
    { id: "STU-104", name: "Ananya Verma", roll: "2023-CSE-005", dept: "Computer Science" },
    { id: "STU-105", name: "Vikram Malhotra", roll: "2023-ECE-034", dept: "Electronics" },
    { id: "STU-106", name: "Sneha Reddy", roll: "2023-ECE-071", dept: "Electronics" },
    { id: "STU-107", name: "Karan Johar", roll: "2023-MECH-012", dept: "Mechanical" },
    { id: "STU-108", name: "Ishaan Gupta", roll: "2023-MECH-055", dept: "Mechanical" }
  ];

  selector.innerHTML = defaultStudents.map(s => `
    <option value="${s.id}">${s.name} (${s.roll}) - ${s.dept}</option>
  `).join("");

  const initialSid = state.selectedPortfolioStudent || "STU-101";
  selector.value = initialSid;
  await loadStudentCompleteWork(initialSid);
}

function inspectStudentWorkFromFee(studentId) {
  state.selectedPortfolioStudent = studentId;
  switchTab("students");
  const selector = document.getElementById("portfolio-student-selector");
  if (selector) selector.value = studentId;
  loadStudentCompleteWork(studentId);
}

async function reloadStudentCompleteWork() {
  const selector = document.getElementById("portfolio-student-selector");
  const sid = selector ? selector.value : (state.selectedPortfolioStudent || "STU-101");
  await loadStudentCompleteWork(sid);
}

async function loadStudentCompleteWork(studentId) {
  state.selectedPortfolioStudent = studentId;
  showGlobalLoader(400);

  try {
    const res = await fetch(`${API_BASE}/students/${studentId}/complete-work`, {
      headers: getAuthHeaders()
    });
    const data = await res.json();
    if (data.success && data.portfolio) {
      state.studentPortfolioData = data.portfolio;
      renderStudentPortfolioView();
    } else {
      showToast(data.error || "Unable to inspect student portfolio.", "error");
    }
  } catch (err) {
    showToast("Error inspecting student work portfolio.", "error");
  }
}

function renderStudentPortfolioView() {
  const container = document.getElementById("student-portfolio-container");
  if (!container || !state.studentPortfolioData) return;

  const pf = state.studentPortfolioData;
  const s = pf.student || {};
  const subs = pf.submissions || [];
  const marks = pf.marks || [];
  const fee = pf.fee || {};

  let riskBadge = "badge-risk-safe";
  if (s.risk_score >= 80) riskBadge = "badge-risk-high";
  else if (s.risk_score >= 50) riskBadge = "badge-risk-med";
  else if (s.risk_score >= 35) riskBadge = "badge-risk-low";

  container.innerHTML = `
    <!-- Student Header Dossier Card -->
    <div class="portfolio-student-header">
      <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap;">
        <div class="portfolio-avatar">${(s.avatar || s.name || 'AS').substring(0, 2).toUpperCase()}</div>
        <div>
          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <h3 style="margin: 0; font-size: 1.25rem;">${s.name}</h3>
            <span class="podium-badge-pill ${riskBadge}">Risk Score: ${s.risk_score || 28.0} (${s.risk_level || 'Low'})</span>
          </div>
          <div style="font-size: 0.82rem; color: var(--text-muted); margin-top: 4px;">
            Roll: <strong>${s.roll_no}</strong> &bull; Dept: <strong>${s.department}</strong> &bull; Semester 6 B.Tech &bull; Mentor: <strong>${s.faculty_mentor || 'Prof. Rajesh Verma'}</strong>
          </div>
        </div>
      </div>
      <div style="display: flex; gap: 8px;">
        <span class="podium-badge-pill badge-risk-safe">Full Authority Active</span>
      </div>
    </div>

    <!-- 4-Card Portfolio Metrics Summary -->
    <div class="portfolio-metrics-grid">
      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Continuous Evaluation CGPA</div>
          <div class="kpi-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
          </div>
        </div>
        <div class="kpi-value">${s.cgpa || '8.4'} / 10.0</div>
        <div class="kpi-subtext">Overall aggregate across all evaluated modules</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Statutory Attendance</div>
          <div class="kpi-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><path d="m9 16 2 2 4-4"/></svg>
          </div>
        </div>
        <div class="kpi-value" style="color: ${s.attendance_overall < 75 ? 'var(--accent-terracotta)' : 'var(--primary)'};">${s.attendance_overall || 82}%</div>
        <div class="kpi-subtext">30-day velocity: ${s.attendance_trend || '+4.2% (Steady)'}</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Coursework Submissions</div>
          <div class="kpi-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><polyline points="9 15 12 18 15 15"/></svg>
          </div>
        </div>
        <div class="kpi-value">${subs.length} Uploads</div>
        <div class="kpi-subtext">Projects and assignments submitted up to 80 MB limit</div>
      </div>

      <div class="kpi-card">
        <div class="kpi-header">
          <div class="kpi-title">Fee Clearance Balance</div>
          <div class="kpi-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
          </div>
        </div>
        <div class="kpi-value" style="color: ${s.fee_dues > 0 ? 'var(--accent-terracotta)' : 'var(--primary)'};">INR ${Number(s.fee_dues || 0).toLocaleString("en-IN")}</div>
        <div class="kpi-subtext">${s.fee_status || 'Clear'}</div>
      </div>
    </div>

    <!-- Complete Work: Submissions & Uploaded Artifacts Ledger (Full Authority) -->
    <div class="marks-ledger-container" style="margin-top: 22px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 8px;">
        <div>
          <h4 style="margin: 0;">Submitted Projects &amp; Coursework Uploads</h4>
          <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 2px;">Faculty authority: Inspect original uploaded documents, check timestamps, and trigger manual AI originality scans.</p>
        </div>
      </div>

      <div class="portfolio-grid">
        ${subs.length === 0 ? `
          <div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 24px;">No coursework files uploaded by this scholar yet.</div>
        ` : subs.map(sub => {
          const aiData = sub.ai_check_data || {};
          const isVerified = aiData.status === "Verified";

          return `
            <div class="portfolio-card">
              <div class="portfolio-card-head">
                <div>
                  <div class="portfolio-card-title">${sub.task_title || sub.task_name || 'Academic Coursework'}</div>
                  <div class="portfolio-card-sub">${sub.course_subject || sub.course || 'Core Subject'} &bull; Type: <strong>${sub.task_type || 'Assignment'}</strong></div>
                </div>
                <span class="podium-badge-pill ${sub.task_type === 'Project' ? 'badge-silver' : 'badge-gold'}">${sub.task_type || 'Assignment'}</span>
              </div>

              <div class="portfolio-file-box">
                <div style="display: flex; align-items: center; gap: 10px;">
                  <div style="width: 32px; height: 32px; border-radius: 6px; background: var(--bg-sand); display: flex; align-items: center; justify-content: center; color: var(--primary);">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                  </div>
                  <div>
                    <div style="font-weight: 700; font-size: 0.84rem;">${sub.file_name}</div>
                    <div style="font-size: 0.72rem; color: var(--text-muted);">Size: ${sub.file_size_mb || '2.4'} MB &bull; Submitted: ${sub.submitted_at || 'Recent'}</div>
                  </div>
                </div>
                <a class="btn btn-secondary btn-sm" href="#" onclick="event.preventDefault(); showToast('Downloading ${sub.file_name}...', 'info');">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                  <span>Download</span>
                </a>
              </div>

              <!-- AI Plagiarism & Originality Verification Block -->
              <div id="ai-results-${sub.id}" style="margin-top: 12px;">
                ${isVerified ? `
                  <div class="ai-verify-panel">
                    <div class="ai-verify-header">
                      <h5>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                        <span>Manual Originality Verification Breakdown</span>
                      </h5>
                      <span style="font-size: 0.72rem; color: var(--text-muted);">${aiData.scanned_at ? aiData.scanned_at.substring(11, 16) : 'Scanned'}</span>
                    </div>

                    <div class="ai-score-bars">
                      <div class="ai-score-bar-human" style="width: ${aiData.human_pct || 72}%;"></div>
                      <div class="ai-score-bar-ai" style="width: ${aiData.ai_pct || 18}%;"></div>
                      <div class="ai-score-bar-copy" style="width: ${aiData.copied_pct || 10}%;"></div>
                    </div>

                    <div class="ai-legend">
                      <span><span class="ai-legend-dot" style="background: var(--primary);"></span> Human: <strong>${aiData.human_pct || 72}%</strong></span>
                      <span><span class="ai-legend-dot" style="background: var(--accent-terracotta);"></span> AI: <strong>${aiData.ai_pct || 18}%</strong></span>
                      <span><span class="ai-legend-dot" style="background: var(--risk-high);"></span> Copy: <strong>${aiData.copied_pct || 10}%</strong></span>
                    </div>
                  </div>
                ` : `
                  <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: var(--bg-sand); border-radius: var(--radius-sm); border: 1px dashed var(--border-color);">
                    <div style="font-size: 0.76rem; color: var(--text-muted);">Originality Scan: <strong>Pending Teacher Manual Verification</strong></div>
                    <button class="btn btn-outline-primary btn-sm" id="btn-ai-scan-${sub.id}" onclick="runManualAICheck('${sub.id}')">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                      <span>Run AI &amp; Copy Verification</span>
                    </button>
                  </div>
                `}
              </div>
            </div>
          `;
        }).join("")}
      </div>
    </div>

    <!-- Marks & Attendance Detailed Ledger -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 22px;">
      <!-- Marks Table -->
      <div class="marks-ledger-container">
        <h4 style="margin-bottom: 12px;">Subject-Wise Continuous Internal Evaluation (CIE)</h4>
        <div class="marks-table-wrap">
          <table class="marks-table">
            <thead>
              <tr>
                <th>Subject</th>
                <th>Midterm</th>
                <th>Coursework</th>
                <th>Total (100)</th>
              </tr>
            </thead>
            <tbody>
              ${marks.length === 0 ? `
                <tr><td>Data Structures</td><td>38</td><td>48</td><td><strong>86 / 100</strong></td></tr>
                <tr><td>Operating Systems</td><td>36</td><td>44</td><td><strong>80 / 100</strong></td></tr>
                <tr><td>DBMS</td><td>35</td><td>43</td><td><strong>78 / 100</strong></td></tr>
                <tr><td>Computer Networks</td><td>34</td><td>40</td><td><strong>74 / 100</strong></td></tr>
              ` : marks.map(m => `
                <tr>
                  <td><strong>${m.subject_name || m.subject_code}</strong></td>
                  <td>${m.assignment_score || 35}</td>
                  <td>${m.attendance_score || 45}</td>
                  <td><strong>${m.total_score} / 100</strong></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Financial Ledger Snapshot -->
      <div class="marks-ledger-container">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h4 style="margin: 0;">Scholar Fee Status &amp; Clearance</h4>
          <span class="podium-badge-pill ${s.fee_dues > 0 ? 'badge-risk-high' : 'badge-risk-safe'}">${fee.status || s.fee_status || 'Clear'}</span>
        </div>
        <div style="font-size: 0.82rem; margin-bottom: 14px;">
          <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-color);">
            <span style="color: var(--text-muted);">Annual Billed Fee:</span>
            <strong>INR ${Number(fee.total_fee || s.fee_dues || 153000).toLocaleString("en-IN")}</strong>
          </div>
          <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--border-color);">
            <span style="color: var(--text-muted);">Paid Amount:</span>
            <strong style="color: var(--primary);">INR ${Number(fee.paid_fee || 105000).toLocaleString("en-IN")}</strong>
          </div>
          <div style="display: flex; justify-content: space-between; padding: 6px 0;">
            <span style="color: var(--text-muted);">Outstanding Balance:</span>
            <strong style="color: var(--accent-terracotta);">INR ${Number(fee.due_fee !== undefined ? fee.due_fee : s.fee_dues).toLocaleString("en-IN")}</strong>
          </div>
        </div>
        ${s.fee_dues > 0 ? `
          <button class="btn btn-terracotta btn-sm" style="width: 100%;" onclick="sendFeeReminder('${s.id}')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
            <span>Dispatch Fee Notice via WhatsApp / Email</span>
          </button>
        ` : `
          <div style="text-align: center; color: var(--primary); font-size: 0.8rem; font-weight: 700; padding: 8px; background: var(--bg-secondary); border-radius: var(--radius-sm);">
            No outstanding fee liabilities. Examination hall-ticket cleared.
          </div>
        `}
      </div>
    </div>
  `;
}

/* ========================================================================== */
/* EAGLEMENTOR AI CHATBOT CONTROLLER                                         */
/* ========================================================================== */

let chatHistory = [];
let isChatOpen = false;
let isChatResponding = false;

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function toggleChatWindow() {
  const chatWin = document.getElementById("ai-chat-window");
  const openIcon = document.getElementById("ai-fab-open-icon");
  const closeIcon = document.getElementById("ai-fab-close-icon");
  const badge = document.getElementById("ai-chat-unread-badge");

  if (!chatWin) return;

  isChatOpen = !isChatOpen;
  if (isChatOpen) {
    chatWin.classList.remove("hidden");
    if (openIcon) openIcon.classList.add("hidden");
    if (closeIcon) closeIcon.classList.remove("hidden");
    if (badge) badge.classList.add("hidden");

    const messagesEl = document.getElementById("ai-chat-messages");
    if (messagesEl && messagesEl.children.length === 0) {
      initChatWelcome();
    }

    const input = document.getElementById("ai-chat-input");
    if (input) setTimeout(() => input.focus(), 150);
  } else {
    chatWin.classList.add("hidden");
    if (openIcon) openIcon.classList.remove("hidden");
    if (closeIcon) closeIcon.classList.add("hidden");
  }
}

function initChatWelcome() {
  const role = (typeof state !== 'undefined' && state.currentUser && state.currentUser.role) ? state.currentUser.role : "Student";
  const name = (typeof state !== 'undefined' && state.currentUser && state.currentUser.name) ? state.currentUser.name : "Scholar";

  const roleIndicator = document.getElementById("ai-chat-role-indicator");
  if (roleIndicator) {
    roleIndicator.textContent = role === "Student" ? "Student Academic Companion" : `${role} Co-Pilot & Cohort Review`;
  }

  let welcomeText = "";
  let initialSuggestions = [];

  if (role === "Student") {
    welcomeText = `Hello **${name}**! I am your **EagleMentor Academic Companion**.\n\nI have your active semester coursework loaded. How may I assist your academic progress today?`;
    initialSuggestions = [
      "What is my attendance status?",
      "Do I have any pending fee dues?",
      "When is my next project deadline?",
      "Explain Dijkstra Algorithm Derivation"
    ];
  } else {
    welcomeText = `Greetings **${name}**! I am your **Faculty & Institutional Co-Pilot**.\n\nDepartment analytics and student cohorts are live. What academic review, student evaluation, or course guidance can I assist you with?`;
    initialSuggestions = [
      "Show students below 75% attendance",
      "Submissions needing AI verification",
      "Cohort fee collection snapshot",
      "Explain NEP 2020 Evaluation Rubrics"
    ];
  }

  appendChatMessage("bot", welcomeText, new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
  renderChatSuggestions(initialSuggestions);
}

function renderChatSuggestions(suggestions) {
  const tray = document.getElementById("ai-chat-suggestions");
  if (!tray) return;

  if (!suggestions || suggestions.length === 0) {
    tray.innerHTML = "";
    return;
  }

  tray.innerHTML = suggestions.map(text => `
    <button type="button" class="ai-chat-chip" onclick="handleSuggestionClick('${text.replace(/'/g, "\\'")}')">
      ${escapeHtml(text)}
    </button>
  `).join("");
}

function handleSuggestionClick(promptText) {
  const input = document.getElementById("ai-chat-input");
  if (input) {
    input.value = promptText;
  }
  handleChatSubmit();
}

function clearChatHistory() {
  const messagesEl = document.getElementById("ai-chat-messages");
  if (messagesEl) messagesEl.innerHTML = "";
  chatHistory = [];
  initChatWelcome();
}

function formatMarkdown(text) {
  if (!text) return "";
  let clean = escapeHtml(text);

  clean = clean.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  clean = clean.replace(/\$\$(.*?)\$\$/g, '<div style="background: var(--bg-secondary); padding: 4px 8px; border-radius: var(--radius-xs); font-family: monospace; font-size: 0.8rem; margin: 4px 0;">$1</div>');
  clean = clean.replace(/\$(.*?)\$/g, '<code style="background: var(--bg-secondary); padding: 1px 3px; border-radius: 3px;">$1</code>');
  clean = clean.replace(/^### (.*$)/gim, '<h4 style="margin: 6px 0 2px 0; font-size: 0.86rem; font-weight: 700; color: var(--text-main);">$1</h4>');
  clean = clean.replace(/^#### (.*$)/gim, '<h5 style="margin: 4px 0 2px 0; font-size: 0.8rem; font-weight: 600; color: var(--primary);">$1</h5>');
  clean = clean.replace(/`([^`]+)`/g, '<code>$1</code>');
  clean = clean.replace(/^\s*\*\s+(.*$)/gim, '<li>$1</li>');
  clean = clean.replace(/(<li>[\s\S]*?<\/li>)/gi, '<ul>$1</ul>');
  clean = clean.replace(/<\/ul>\s*<ul>/g, '');
  clean = clean.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li>$2</li>');
  clean = clean.replace(/\n\n+/g, '<br><br>');
  clean = clean.replace(/(?<!<br>)\n/g, '<br>');

  return clean;
}

function appendChatMessage(role, text, timeStr) {
  const messagesEl = document.getElementById("ai-chat-messages");
  if (!messagesEl) return;

  const bubble = document.createElement("div");
  bubble.className = `ai-chat-bubble ${role}`;

  const time = timeStr || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  if (role === "user") {
    bubble.innerHTML = `
      <div>${escapeHtml(text)}</div>
      <span class="ai-chat-time">${time}</span>
    `;
  } else {
    bubble.innerHTML = `
      <div>${formatMarkdown(text)}</div>
      <span class="ai-chat-time">${time}</span>
    `;
  }

  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function showChatTypingIndicator() {
  const messagesEl = document.getElementById("ai-chat-messages");
  if (!messagesEl) return null;

  const indicator = document.createElement("div");
  indicator.id = "ai-chat-typing-indicator";
  indicator.className = "ai-chat-typing";
  indicator.innerHTML = `
    <span class="ai-chat-dot"></span>
    <span class="ai-chat-dot"></span>
    <span class="ai-chat-dot"></span>
  `;
  messagesEl.appendChild(indicator);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return indicator;
}

function removeChatTypingIndicator() {
  const indicator = document.getElementById("ai-chat-typing-indicator");
  if (indicator) indicator.remove();
}

async function handleChatSubmit(event) {
  if (event) event.preventDefault();
  if (isChatResponding) return;

  const input = document.getElementById("ai-chat-input");
  if (!input) return;

  const msg = input.value.trim();
  if (!msg) return;

  input.value = "";

  const timeNow = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  appendChatMessage("user", msg, timeNow);
  chatHistory.push({ role: "user", content: msg });

  isChatResponding = true;
  showChatTypingIndicator();

  const token = typeof state !== 'undefined' ? state.token : null;
  const currentRole = (typeof state !== 'undefined' && state.currentUser && state.currentUser.role) ? state.currentUser.role : "Student";
  const studentId = (typeof state !== 'undefined' && state.currentUser && state.currentUser.student_id) ? state.currentUser.student_id : "STU-101";

  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({
        message: msg,
        history: chatHistory.slice(-6),
        role: currentRole,
        student_id: studentId
      })
    });

    removeChatTypingIndicator();
    isChatResponding = false;

    if (res.ok) {
      const data = await res.json();
      const replyText = data.reply || "I have processed your query with our academic ledger.";
      const botTime = data.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      appendChatMessage("bot", replyText, botTime);
      chatHistory.push({ role: "assistant", content: replyText });
      if (data.suggestions && data.suggestions.length > 0) {
        renderChatSuggestions(data.suggestions);
      }
    } else {
      const err = await res.json();
      appendChatMessage("bot", `I encountered a momentary issue: ${err.error || "Unable to reach academic copilot service."}`);
    }
  } catch (err) {
    removeChatTypingIndicator();
    isChatResponding = false;
    appendChatMessage("bot", "Network connection to EagleMentor AI timed out. Please check your connection and try again.");
  }
}

// ==========================================================================
// EXTENDED MODULES: REGISTRATION, PROFILE, TESTS, WELLBEING, CLAIMS & NOTIFS
// ==========================================================================

// 1. Student Registration & Profile Management
function toggleStudentAuthView(mode) {
  const loginForm = document.getElementById("student-login-form-container");
  const regForm = document.getElementById("student-register-form-container");
  const title = document.getElementById("gateway-login-title");
  const sub = document.getElementById("gateway-login-sub");

  if (mode === "register") {
    if (loginForm) loginForm.style.display = "none";
    if (regForm) regForm.style.display = "block";
    if (title) title.textContent = "New Student Registration";
    if (sub) sub.textContent = "Create your academic profile to access your student workspace and marks ledger:";
  } else {
    if (loginForm) loginForm.style.display = "block";
    if (regForm) regForm.style.display = "none";
    if (title) title.textContent = "Student Portal Sign In";
    if (sub) sub.textContent = "Enter your University Roll Number / Student ID and password to access your academic workspace:";
  }
}

function selectRegAvatar(btn, avatar) {
  document.querySelectorAll("#reg-avatar-picker .avatar-choice-chip").forEach(c => c.classList.remove("selected"));
  btn.classList.add("selected");
  const valInput = document.getElementById("reg-avatar-val");
  if (valInput) valInput.value = avatar;
}

async function submitStudentRegister() {
  const name = document.getElementById("reg-name").value.trim();
  const roll = document.getElementById("reg-roll").value.trim();
  const email = document.getElementById("reg-email").value.trim();
  const phone = document.getElementById("reg-phone").value.trim();
  const dept = document.getElementById("reg-dept").value;
  const year = parseInt(document.getElementById("reg-year").value, 10) || 3;
  const genderInput = document.querySelector('input[name="reg-gender"]:checked');
  const gender = genderInput ? genderInput.value : "Male";
  const avatar = document.getElementById("reg-avatar-val").value || "AS";
  const pwd = document.getElementById("reg-pwd").value;
  const pwdConfirm = document.getElementById("reg-pwd-confirm").value;

  if (!name || !roll || !email || !pwd) {
    showToast("Please fill all required registration fields.", "warning");
    return;
  }
  if (pwd !== pwdConfirm) {
    showToast("Passwords do not match.", "warning");
    return;
  }

  setBtnLoading("btn-student-register", true, "Creating Account...");
  showGlobalLoader(600);

  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name,
        roll_no: roll,
        email: email,
        phone: phone || `+9198765${Math.floor(10000 + Math.random() * 90000)}`,
        department: dept,
        year: year,
        gender: gender,
        avatar: avatar,
        password: pwd
      })
    });
    const data = await res.json();
    if (data.success) {
      state.currentUser = data.user;
      state.token = data.token;
      state.isAuthenticated = true;
      sessionStorage.setItem("edueagle_auth_user", JSON.stringify(data.user));
      sessionStorage.setItem("edueagle_auth_token", data.token);
      updateUserUI();
      hideLoginScreen();
      showToast(`Student profile created! Welcome to EduEagle, ${data.user.name}.`, "success", "Registered");
      switchTab("podium");
      await loadInitialData();
    } else {
      showToast(data.error || "Registration failed.", "error");
    }
  } catch (err) {
    showToast("Network error during registration.", "error");
  } finally {
    setBtnLoading("btn-student-register", false);
  }
}

function openStudentProfileModal() {
  if (!state.currentUser) return;
  const nameInput = document.getElementById("profile-input-name");
  const rollInput = document.getElementById("profile-input-roll");
  const deptInput = document.getElementById("profile-input-dept");
  const yearInput = document.getElementById("profile-input-year");
  const avatarPreview = document.getElementById("profile-modal-avatar-preview");
  const avatarVal = document.getElementById("profile-avatar-val");

  if (nameInput) nameInput.value = state.currentUser.name || "";
  if (rollInput) rollInput.value = state.currentUser.student_id || state.currentUser.id || "STU-101";
  if (deptInput && state.currentUser.department) deptInput.value = state.currentUser.department;
  if (yearInput && state.currentUser.year) yearInput.value = state.currentUser.year;
  if (avatarPreview) avatarPreview.textContent = state.currentUser.avatar || "AS";
  if (avatarVal) avatarVal.value = state.currentUser.avatar || "AS";

  document.querySelectorAll("#profile-avatar-picker .avatar-choice-chip").forEach(c => {
    c.classList.toggle("selected", c.textContent.trim() === (state.currentUser.avatar || "AS"));
  });

  const gender = state.currentUser.gender || "Male";
  const genderRadio = document.querySelector(`input[name="profile-gender"][value="${gender}"]`);
  if (genderRadio) genderRadio.checked = true;

  openModal("modal-student-profile");
}

function selectProfileAvatar(btn, avatar) {
  document.querySelectorAll("#profile-avatar-picker .avatar-choice-chip").forEach(c => c.classList.remove("selected"));
  btn.classList.add("selected");
  const valInput = document.getElementById("profile-avatar-val");
  const preview = document.getElementById("profile-modal-avatar-preview");
  if (valInput) valInput.value = avatar;
  if (preview) preview.textContent = avatar;
}

async function saveStudentProfile() {
  const name = document.getElementById("profile-input-name").value.trim();
  const dept = document.getElementById("profile-input-dept").value;
  const year = parseInt(document.getElementById("profile-input-year").value, 10) || 3;
  const genderInput = document.querySelector('input[name="profile-gender"]:checked');
  const gender = genderInput ? genderInput.value : "Male";
  const avatar = document.getElementById("profile-avatar-val").value || "AS";

  if (!name) {
    showToast("Please provide your name.", "warning");
    return;
  }

  setBtnLoading("btn-save-student-profile", true, "Saving...");
  try {
    const res = await fetch(`${API_BASE}/students/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name,
        department: dept,
        year: year,
        gender: gender,
        avatar: avatar
      })
    });
    const data = await res.json();
    if (data.success) {
      state.currentUser = { ...state.currentUser, ...data.student, name: name, avatar: avatar };
      sessionStorage.setItem("edueagle_auth_user", JSON.stringify(state.currentUser));
      updateUserUI();
      closeModal("modal-student-profile");
      showToast("Profile details updated successfully!", "success", "Profile Saved");
    } else {
      showToast(data.error || "Failed to update profile.", "error");
    }
  } catch (err) {
    showToast("Error updating profile.", "error");
  } finally {
    setBtnLoading("btn-save-student-profile", false);
  }
}

// 2. Notification Center & Scheduler Logs
async function fetchNotifications() {
  try {
    const res = await fetch(`${API_BASE}/notifications`);
    const data = await res.json();
    state.userNotifications = data.notifications || [];
    renderNotificationsUI();
  } catch (err) {
    console.error("Error fetching notifications:", err);
  }
}

function renderNotificationsUI() {
  const badge = document.getElementById("notif-badge-count");
  const listContainer = document.getElementById("notification-list-container");
  if (!badge || !listContainer) return;

  const notifs = state.userNotifications || [];
  const unreadCount = notifs.filter(n => !n.is_read).length;

  if (unreadCount > 0) {
    badge.textContent = unreadCount;
    badge.style.display = "inline-block";
  } else {
    badge.style.display = "none";
  }

  if (notifs.length === 0) {
    listContainer.innerHTML = `<div style="text-align: center; padding: 18px; color: var(--text-muted); font-size: 0.8rem;">No notifications right now</div>`;
    return;
  }

  listContainer.innerHTML = notifs.map(n => `
    <div class="notif-item ${!n.is_read ? 'is-unread' : ''}" onclick="markNotificationRead('${n.id}')">
      <div class="notif-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
      </div>
      <div style="flex: 1;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <strong style="font-size: 0.78rem; color: var(--text-main);">${n.title}</strong>
          <span style="font-size: 0.68rem; color: var(--text-muted);">${n.timestamp ? n.timestamp.split('T')[0] : ''}</span>
        </div>
        <p style="font-size: 0.74rem; color: var(--text-muted); margin: 2px 0 0 0; line-height: 1.35;">${n.message}</p>
      </div>
    </div>
  `).join("");
}

function toggleNotificationDropdown() {
  const dropdown = document.getElementById("notification-dropdown");
  if (!dropdown) return;
  const isHidden = dropdown.style.display === "none" || dropdown.style.display === "";
  dropdown.style.display = isHidden ? "flex" : "none";
  if (isHidden) fetchNotifications();
}

async function markNotificationRead(notifId) {
  try {
    await fetch(`${API_BASE}/notifications/${notifId}/read`, { method: "POST" });
    const target = (state.userNotifications || []).find(n => n.id === notifId);
    if (target) target.is_read = true;
    renderNotificationsUI();
  } catch (err) {
    console.error("Error marking notification read:", err);
  }
}

async function clearAllNotifications() {
  try {
    await fetch(`${API_BASE}/notifications/clear-all`, { method: "POST" });
    state.userNotifications = [];
    renderNotificationsUI();
    showToast("Notifications cleared.", "info");
  } catch (err) {
    showToast("Error clearing notifications.", "error");
  }
}

// 3. Timed Mock Assessments & Tests
async function fetchMockTests() {
  try {
    const [testsRes, historyRes] = await Promise.all([
      fetch(`${API_BASE}/mock-tests`),
      fetch(`${API_BASE}/mock-tests/history/my`)
    ]);
    const testsData = await testsRes.json();
    const historyData = await historyRes.json();

    state.mockTests = testsData.mock_tests || [];
    state.testHistory = historyData.history || [];
    renderMockTestsView();
  } catch (err) {
    console.error("Error fetching mock tests:", err);
  }
}

function renderMockTestsView() {
  const container = document.getElementById("mock-tests-container");
  const historyTbody = document.getElementById("mock-test-history-tbody");
  if (!container) return;

  const isStudent = state.currentUser.role === "Student";
  const tests = state.mockTests || [];

  if (tests.length === 0) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 24px; color: var(--text-muted);">No mock assessments published yet.</div>`;
  } else {
    container.innerHTML = tests.map(t => `
      <div class="mock-test-card">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
            <span class="topic-tag">${t.subject}</span>
            <span style="font-size: 0.74rem; font-weight: 700; color: var(--primary);">${t.duration_minutes} Mins</span>
          </div>
          <h4 style="margin: 4px 0 6px 0; font-size: 1rem;">${t.title}</h4>
          <p style="font-size: 0.78rem; color: var(--text-muted); line-height: 1.45; margin-bottom: 12px;">${t.instructions || 'Standard curriculum assessment with automated scoring and topic performance breakdown.'}</p>
        </div>
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 0.74rem; color: var(--text-subtle); margin-bottom: 10px;">
            <span>Questions: <strong>${t.question_count || (t.questions ? t.questions.length : 5)}</strong></span>
            <span>Total: <strong>${t.total_marks || 25} Marks</strong></span>
          </div>
          <button class="btn btn-primary" style="width: 100%; justify-content: center;" onclick="startMockTest('${t.id}')">
            <span>Start Assessment</span>
          </button>
        </div>
      </div>
    `).join("");
  }

  if (historyTbody) {
    const history = state.testHistory || [];
    if (history.length === 0) {
      historyTbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 18px; color: var(--text-muted);">No assessments taken yet. Start an assessment above!</td></tr>`;
    } else {
      historyTbody.innerHTML = history.map(h => `
        <tr>
          <td><code>${h.test_id || h.id}</code></td>
          <td><strong>${h.title || 'Curriculum Assessment'}</strong></td>
          <td>${h.subject || 'Core Engineering'}</td>
          <td><strong>${h.score_obtained} / ${h.total_marks}</strong></td>
          <td><span class="podium-badge-pill ${h.accuracy_rate >= 75 ? 'badge-risk-safe' : 'badge-risk-low'}">${h.accuracy_rate}%</span></td>
          <td>${Math.floor((h.time_taken_seconds || 0) / 60)}m ${(h.time_taken_seconds || 0) % 60}s</td>
          <td><span class="podium-badge-pill badge-project">${h.speed_accuracy_rating || 'Balanced'}</span></td>
          <td><span style="font-size: 0.74rem; color: var(--text-muted);">${h.submitted_at ? h.submitted_at.split('T')[0] : 'Recent'}</span></td>
        </tr>
      `).join("");
    }
  }
}

function toggleFacultyCreateTestPanel(show) {
  const panel = document.getElementById("faculty-create-test-panel");
  if (panel) panel.style.display = show ? "block" : "none";
}

async function submitCreateMockTest() {
  const title = document.getElementById("test-create-title").value.trim();
  const subject = document.getElementById("test-create-subject").value;
  const duration = parseInt(document.getElementById("test-create-duration").value, 10) || 15;
  const instructions = document.getElementById("test-create-instructions").value.trim();
  const jsonRaw = document.getElementById("test-create-questions-json").value.trim();

  let questions = null;
  if (jsonRaw) {
    try {
      questions = JSON.parse(jsonRaw);
    } catch (e) {
      showToast("Invalid JSON in questions field. Please check formatting.", "warning");
      return;
    }
  }

  setBtnLoading("btn-save-mock-test", true, "Publishing...");
  try {
    const res = await fetch(`${API_BASE}/mock-tests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title,
        subject: subject,
        duration_minutes: duration,
        instructions: instructions,
        questions: questions
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Mock Assessment '${title}' published!`, "success", "Assessment Published");
      toggleFacultyCreateTestPanel(false);
      await fetchMockTests();
    } else {
      showToast(data.error || "Failed to publish assessment.", "error");
    }
  } catch (err) {
    showToast("Error creating mock test.", "error");
  } finally {
    setBtnLoading("btn-save-mock-test", false);
  }
}

async function startMockTest(testId) {
  showGlobalLoader(400);
  try {
    const res = await fetch(`${API_BASE}/mock-tests/${testId}/start`, { method: "POST" });
    const data = await res.json();
    if (!data.success) {
      showToast(data.error || "Could not start assessment.", "error");
      return;
    }

    state.activeTest = data.test;
    state.testAnswers = {};
    state.testDurationSeconds = (data.test.duration_minutes || 15) * 60;
    state.testRemainingSeconds = state.testDurationSeconds;
    state.testStartTime = Date.now();

    // Populate Active Test UI
    const titleEl = document.getElementById("active-test-title");
    const subEl = document.getElementById("active-test-subject");
    const questionsContainer = document.getElementById("active-test-questions-list");
    const testUi = document.getElementById("mock-test-active-interface");

    if (titleEl) titleEl.textContent = data.test.title;
    if (subEl) subEl.textContent = `${data.test.subject} • ${data.test.duration_minutes} Mins • Total ${data.test.total_marks || 25} Marks`;

    if (questionsContainer) {
      questionsContainer.innerHTML = (data.test.questions || []).map((q, idx) => `
        <div class="test-question-box">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-weight: 700; font-size: 0.88rem; color: var(--text-main);">Question ${idx + 1}: ${q.topic ? `<span class="topic-tag">${q.topic}</span>` : ''}</span>
            <span style="font-size: 0.74rem; font-weight: 700; color: var(--primary);">${q.marks || 5} Marks</span>
          </div>
          <p style="font-size: 0.84rem; color: var(--text-main); margin-bottom: 12px; line-height: 1.45;">${q.prompt}</p>
          <div>
            ${(q.options || []).map((opt, optIdx) => `
              <label class="test-option-item">
                <input type="radio" name="question-${q.id}" value="${optIdx}" onchange="onSelectTestAnswer('${q.id}', ${optIdx})">
                <span style="font-size: 0.82rem;">${opt}</span>
              </label>
            `).join("")}
          </div>
        </div>
      `).join("");
    }

    if (testUi) testUi.style.display = "block";
    testUi.scrollIntoView({ behavior: "smooth", block: "start" });

    // Setup Countdown Timer
    if (state.testTimerInterval) clearInterval(state.testTimerInterval);
    updateTimerDisplay();

    state.testTimerInterval = setInterval(() => {
      state.testRemainingSeconds -= 1;
      updateTimerDisplay();

      if (state.testRemainingSeconds <= 0) {
        clearInterval(state.testTimerInterval);
        showToast("Time expired! Automatically submitting your assessment...", "warning", "Time Expired");
        submitMockTest();
      }
    }, 1000);

  } catch (err) {
    showToast("Error starting assessment session.", "error");
  }
}

function updateTimerDisplay() {
  const clockEl = document.getElementById("mock-timer-clock");
  const textEl = document.getElementById("mock-timer-text");
  if (!textEl) return;

  const mins = Math.floor(Math.max(0, state.testRemainingSeconds) / 60);
  const secs = Math.max(0, state.testRemainingSeconds) % 60;
  textEl.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

  if (clockEl) {
    if (state.testRemainingSeconds <= 120) {
      clockEl.classList.add("timer-urgent");
    } else {
      clockEl.classList.remove("timer-urgent");
    }
  }
}

function onSelectTestAnswer(qId, optIdx) {
  state.testAnswers[qId] = optIdx;
}

function confirmSubmitMockTest() {
  const answeredCount = Object.keys(state.testAnswers || {}).length;
  const totalCount = (state.activeTest && state.activeTest.questions) ? state.activeTest.questions.length : 0;
  if (answeredCount < totalCount) {
    if (!confirm(`You have answered ${answeredCount} of ${totalCount} questions. Are you sure you want to submit?`)) {
      return;
    }
  }
  submitMockTest();
}

async function submitMockTest() {
  if (state.testTimerInterval) {
    clearInterval(state.testTimerInterval);
    state.testTimerInterval = null;
  }

  if (!state.activeTest) return;
  const testId = state.activeTest.id;
  const timeTaken = Math.min(state.testDurationSeconds, Math.floor((Date.now() - state.testStartTime) / 1000));

  setBtnLoading("btn-submit-active-test", true, "Submitting...");
  showGlobalLoader(700);

  try {
    const res = await fetch(`${API_BASE}/mock-tests/${testId}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        answers: state.testAnswers || {},
        time_taken_seconds: timeTaken
      })
    });
    const data = await res.json();
    if (data.success) {
      // Hide active test UI
      const testUi = document.getElementById("mock-test-active-interface");
      if (testUi) testUi.style.display = "none";

      // Show result card
      const resultCard = document.getElementById("mock-test-result-card");
      if (resultCard) {
        document.getElementById("result-score-val").textContent = `${data.score_obtained} / ${data.total_marks}`;
        document.getElementById("result-accuracy-val").textContent = `${data.accuracy_rate}%`;
        document.getElementById("result-time-val").textContent = `${Math.floor(timeTaken / 60)}m ${timeTaken % 60}s`;
        document.getElementById("result-rating-val").textContent = data.speed_accuracy_rating || "Balanced";

        const topicDiv = document.getElementById("result-topic-breakdown");
        if (topicDiv && data.topic_breakdown) {
          topicDiv.innerHTML = Object.entries(data.topic_breakdown).map(([top, stat]) => `
            <div style="background: var(--bg-sand); padding: 6px 12px; border-radius: var(--radius-sm); border: 1px solid var(--border-color); font-size: 0.76rem;">
              <strong>${top}:</strong> ${stat.correct}/${stat.total} (${stat.accuracy}%)
            </div>
          `).join("");
        }

        resultCard.style.display = "block";
        resultCard.scrollIntoView({ behavior: "smooth", block: "start" });
      }

      showToast(`Assessment completed! Score: ${data.score_obtained}/${data.total_marks} (${data.accuracy_rate}%)`, "success", "Assessment Evaluated");
      await fetchMockTests();
      await fetchRewardClaimsDesk();
    } else {
      showToast(data.error || "Submission failed.", "error");
    }
  } catch (err) {
    showToast("Error submitting assessment.", "error");
  } finally {
    setBtnLoading("btn-submit-active-test", false);
  }
}

function closeMockTestResult() {
  const card = document.getElementById("mock-test-result-card");
  if (card) card.style.display = "none";
}

// 4. Confidential Student Well-Being Hub
async function renderWellbeingView() {
  const tbody = document.getElementById("wellbeing-history-tbody");
  if (!tbody) return;

  try {
    const res = await fetch(`${API_BASE}/wellbeing/history`);
    const data = await res.json();
    state.wellbeingHistory = data.history || [];

    if (state.wellbeingHistory.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 18px; color: var(--text-muted);">No check-ins recorded yet. Record your first private check-in above!</td></tr>`;
      return;
    }

    tbody.innerHTML = state.wellbeingHistory.map(entry => `
      <tr>
        <td><strong>${entry.timestamp ? entry.timestamp.split('T')[0] : 'Recent'}</strong> <span style="font-size: 0.72rem; color: var(--text-muted);">${entry.timestamp ? entry.timestamp.split('T')[1].substring(0, 5) : ''}</span></td>
        <td><span class="podium-badge-pill badge-project">${entry.mood}</span></td>
        <td>${entry.stress_level} / 5</td>
        <td>${entry.sleep_hours} hrs</td>
        <td>${entry.energy_level} / 5</td>
        <td><span style="font-size: 0.78rem; color: var(--text-muted);">${entry.notes || '-'}</span></td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Error loading wellbeing history:", err);
  }
}

function selectMood(btn, mood) {
  document.querySelectorAll("#mood-selector-options .mood-btn").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");
  const input = document.getElementById("wellbeing-mood-val");
  if (input) input.value = mood;
}

async function submitWellbeingCheckin() {
  const mood = document.getElementById("wellbeing-mood-val").value || "Good";
  const stress = parseInt(document.getElementById("wellbeing-stress-val").value, 10) || 3;
  const sleep = parseFloat(document.getElementById("wellbeing-sleep-val").value) || 7.0;
  const energy = parseInt(document.getElementById("wellbeing-energy-val").value, 10) || 3;
  const notes = document.getElementById("wellbeing-notes-val").value.trim();

  setBtnLoading("btn-submit-wellbeing", true, "Recording...");
  try {
    const res = await fetch(`${API_BASE}/wellbeing/checkin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mood: mood,
        stress_level: stress,
        sleep_hours: sleep,
        energy_level: energy,
        notes: notes
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast("Check-in saved securely. Stay mindful and take regular breaks!", "success", "Well-Being Recorded");
      
      const feedbackDiv = document.getElementById("wellbeing-instant-feedback");
      const feedbackText = document.getElementById("wellbeing-feedback-text");
      if (feedbackDiv && feedbackText && data.suggestion) {
        feedbackText.textContent = data.suggestion;
        feedbackDiv.style.display = "block";
      }

      document.getElementById("wellbeing-notes-val").value = "";
      await renderWellbeingView();
    } else {
      showToast(data.error || "Failed to save check-in.", "error");
    }
  } catch (err) {
    showToast("Error recording check-in.", "error");
  } finally {
    setBtnLoading("btn-submit-wellbeing", false);
  }
}

// 5. Merit Rewards & Claims Desk
async function fetchRewardClaimsDesk() {
  try {
    const [pointsRes, claimsRes] = await Promise.all([
      fetch(`${API_BASE}/rewards/my-points`),
      fetch(`${API_BASE}/rewards/claims`)
    ]);
    const pointsData = await pointsRes.json();
    const claimsData = await claimsRes.json();

    state.rewardPoints = pointsData;
    state.userClaims = claimsData.claims || [];
    renderRewardClaimsDesk();
  } catch (err) {
    console.error("Error fetching reward claims desk:", err);
  }
}

function renderRewardClaimsDesk() {
  const pointsEl = document.getElementById("my-reward-points-total");
  const rankEl = document.getElementById("my-reward-rank-display");
  const eligEl = document.getElementById("my-reward-eligibility-display");
  const tbody = document.getElementById("reward-claims-tbody");
  const isFaculty = state.currentUser && (state.currentUser.role === "Faculty" || state.currentUser.role === "HOD" || state.currentUser.role === "Admin");

  if (pointsEl && state.rewardPoints) {
    pointsEl.textContent = `${state.rewardPoints.total_points || 0} Pts`;
  }
  if (rankEl && state.rewardPoints) {
    rankEl.textContent = state.rewardPoints.rank ? `Rank #${state.rewardPoints.rank}` : "Rank #--";
  }
  if (eligEl && state.rewardPoints) {
    if (state.rewardPoints.rank && state.rewardPoints.rank <= 3) {
      eligEl.textContent = `Eligible: Top ${state.rewardPoints.rank} Podium Honor`;
      eligEl.style.color = "var(--risk-safe)";
    } else {
      eligEl.textContent = "Standard Points Tier";
      eligEl.style.color = "var(--text-muted)";
    }
  }

  if (tbody) {
    const claims = state.userClaims || [];
    if (claims.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 18px; color: var(--text-muted);">No reward claims filed yet. Top scholars can claim awards above!</td></tr>`;
      return;
    }

    tbody.innerHTML = claims.map(c => {
      let statusBadge = `<span class="podium-badge-pill badge-risk-low">${c.status}</span>`;
      if (c.status === "Approved") statusBadge = `<span class="podium-badge-pill badge-risk-safe">Approved</span>`;
      else if (c.status === "Redeemed") statusBadge = `<span class="podium-badge-pill badge-project">Redeemed</span>`;
      else if (c.status === "Rejected") statusBadge = `<span class="podium-badge-pill badge-risk-high">Rejected</span>`;

      let actionHtml = `-`;
      if (isFaculty && c.status === "Pending") {
        actionHtml = `
          <div style="display: flex; gap: 4px;">
            <button class="btn btn-primary btn-sm" style="font-size: 0.7rem; padding: 2px 6px;" onclick="processRewardClaimAction('${c.id}', 'Approved')">Approve</button>
            <button class="btn btn-secondary btn-sm" style="font-size: 0.7rem; padding: 2px 6px;" onclick="processRewardClaimAction('${c.id}', 'Redeemed')">Redeem</button>
          </div>
        `;
      } else if (c.voucher_code) {
        actionHtml = `<code>${c.voucher_code}</code>`;
      }

      return `
        <tr>
          <td><code>${c.id}</code></td>
          <td><strong>${c.student_name || 'Student'}</strong></td>
          <td>Rank #${c.rank || 1}</td>
          <td>${c.reward_tier_name || 'Academic Merit Grant'}</td>
          <td><code>${c.voucher_code || 'Pending'}</code></td>
          <td>${statusBadge}</td>
          <td><span style="font-size: 0.74rem; color: var(--text-muted);">${c.claimed_at ? c.claimed_at.split('T')[0] : 'Recent'}</span></td>
          <td>${actionHtml}</td>
        </tr>
      `;
    }).join("");
  }
}

function openRewardClaimModal() {
  openModal("modal-claim-reward");
}

async function submitRewardClaimAction() {
  const tier = document.getElementById("claim-reward-tier-select").value;
  const pref = document.getElementById("claim-disbursement-pref").value;
  const notes = document.getElementById("claim-notes-input").value.trim();

  setBtnLoading("btn-submit-claim", true, "Submitting Claim...");
  try {
    const res = await fetch(`${API_BASE}/rewards/claim`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rank: parseInt(tier, 10) || 1,
        reward_tier_name: tier === "1" ? "Gold Laureate" : tier === "2" ? "Silver Scholar" : "Bronze Distinction",
        disbursement_preference: pref,
        claim_notes: notes
      })
    });
    const data = await res.json();
    if (data.success) {
      closeModal("modal-claim-reward");
      showToast(`Merit Reward claim submitted! Claim ID: ${data.claim.id}. Voucher: ${data.claim.voucher_code}`, "success", "Claim Filed");
      await fetchRewardClaimsDesk();
    } else {
      showToast(data.error || "Failed to submit claim.", "error");
    }
  } catch (err) {
    showToast("Error submitting claim.", "error");
  } finally {
    setBtnLoading("btn-submit-claim", false);
  }
}

async function processRewardClaimAction(claimId, newStatus) {
  showGlobalLoader(400);
  try {
    const res = await fetch(`${API_BASE}/rewards/claims/${claimId}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: newStatus,
        admin_notes: `Processed by ${state.currentUser.name} (${state.currentUser.role})`
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Claim ${claimId} transitioned to ${newStatus}.`, "success", "Claim Processed");
      await fetchRewardClaimsDesk();
    } else {
      showToast(data.error || "Failed to process claim.", "error");
    }
  } catch (err) {
    showToast("Error processing claim.", "error");
  }
}

// 6. Evaluation Appeals Desk
async function fetchAppeals() {
  try {
    const res = await fetch(`${API_BASE}/assignment-appeals`);
    const data = await res.json();
    state.userAppeals = data.appeals || [];
    renderAppealsList();
  } catch (err) {
    console.error("Error fetching assignment appeals:", err);
  }
}

function renderAppealsList() {
  const tbody = document.getElementById("appeals-table-tbody");
  if (!tbody) return;

  const appeals = state.userAppeals || [];
  if (appeals.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 18px; color: var(--text-muted);">No student evaluation appeals currently pending review.</td></tr>`;
    return;
  }

  tbody.innerHTML = appeals.map(a => `
    <tr>
      <td><code>${a.id}</code></td>
      <td><strong>${a.student_id}</strong></td>
      <td>${a.category || 'Grading Review'}</td>
      <td><span style="font-size: 0.78rem;">${a.reason}</span></td>
      <td><span class="podium-badge-pill ${a.status === 'Resolved' ? 'badge-risk-safe' : 'badge-risk-low'}">${a.status}</span></td>
      <td><span style="font-size: 0.74rem; color: var(--text-muted);">${a.created_at ? a.created_at.split('T')[0] : 'Recent'}</span></td>
      <td>
        ${a.status === 'Pending' ? `
          <div style="display: flex; gap: 4px;">
            <button class="btn btn-primary btn-sm" style="font-size: 0.7rem; padding: 2px 6px;" onclick="reviewAppealAction('${a.id}', 'Resolved')">Resolve</button>
            <button class="btn btn-secondary btn-sm" style="font-size: 0.7rem; padding: 2px 6px;" onclick="reviewAppealAction('${a.id}', 'Rejected')">Reject</button>
          </div>
        ` : `<span style="font-size: 0.72rem; color: var(--text-muted);">${a.resolution_notes || 'Reviewed'}</span>`}
      </td>
    </tr>
  `).join("");
}

function openAppealModal(submissionId, taskTitle) {
  const idInput = document.getElementById("appeal-submission-id");
  const subTitle = document.getElementById("appeal-modal-subtitle");
  if (idInput) idInput.value = submissionId;
  if (subTitle && taskTitle) subTitle.textContent = `Review Request for: ${taskTitle}`;
  openModal("modal-submit-appeal");
}

async function submitAppealAction() {
  const submissionId = document.getElementById("appeal-submission-id").value;
  const category = document.getElementById("appeal-category-select").value;
  const reason = document.getElementById("appeal-reason-input").value.trim();

  if (!reason) {
    showToast("Please provide the detailed reason for your appeal.", "warning");
    return;
  }

  setBtnLoading("btn-submit-appeal-action", true, "Submitting...");
  try {
    const res = await fetch(`${API_BASE}/submissions/${submissionId}/appeal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category: category,
        reason: reason
      })
    });
    const data = await res.json();
    if (data.success) {
      closeModal("modal-submit-appeal");
      showToast("Evaluation appeal submitted! Faculty committee will review your handwritten proof.", "success", "Appeal Submitted");
      if (state.currentUser && state.currentUser.role !== "Student") await fetchAppeals();
    } else {
      showToast(data.error || "Failed to submit appeal.", "error");
    }
  } catch (err) {
    showToast("Error submitting appeal.", "error");
  } finally {
    setBtnLoading("btn-submit-appeal-action", false);
  }
}

async function reviewAppealAction(appealId, resolution) {
  showGlobalLoader(400);
  try {
    const res = await fetch(`${API_BASE}/assignment-appeals/${appealId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: resolution,
        resolution_notes: `Reviewed and marked ${resolution} by ${state.currentUser.name} (${state.currentUser.role})`
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Appeal marked as ${resolution}.`, "success", "Appeal Reviewed");
      await fetchAppeals();
    } else {
      showToast(data.error || "Failed to review appeal.", "error");
    }
  } catch (err) {
    showToast("Error reviewing appeal.", "error");
  }
}
