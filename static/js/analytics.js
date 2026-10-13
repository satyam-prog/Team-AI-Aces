/**
 * EduEagle Privacy-Preserving Institutional Telemetry & Analytics Engine
 * Compliant with FERPA educational record privacy mandates.
 * Zero third-party tracker cookies. Honors browser Do Not Track (DNT) signal.
 */

(function () {
  const STORAGE_KEY = "edueagle_cookie_consent";
  const ANALYTICS_ENDPOINT = "/api/analytics/event";

  const EagleAnalytics = {
    isDntEnabled: function () {
      return (
        navigator.doNotTrack === "1" ||
        window.doNotTrack === "1" ||
        navigator.msDoNotTrack === "1"
      );
    },

    getConsent: function () {
      return localStorage.getItem(STORAGE_KEY);
    },

    track: function (eventName, eventProps) {
      if (this.isDntEnabled()) {
        console.debug("[Analytics] Telemetry suppressed (Do Not Track active).");
        return;
      }

      const consent = this.getConsent();
      if (consent === "declined") {
        console.debug("[Analytics] Telemetry suppressed (Consent declined).");
        return;
      }

      const payload = {
        event: eventName,
        path: window.location.pathname,
        timestamp: new Date().toISOString(),
        referrer: document.referrer || "direct",
        viewport: `${window.innerWidth}x${window.innerHeight}`,
        properties: eventProps || {}
      };

      // Asynchronous dispatch via fetch or beacon
      try {
        if (navigator.sendBeacon) {
          navigator.sendBeacon(ANALYTICS_ENDPOINT, JSON.stringify(payload));
        } else {
          fetch(ANALYTICS_ENDPOINT, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            keepalive: true
          }).catch(() => {});
        }
      } catch (e) {
        // Non-blocking telemetry
      }
    },

    init: function () {
      // Auto-track initial landing page view
      this.track("page_view", {
        title: document.title,
        url: window.location.href
      });

      // Track visibility and SPA navigation
      window.addEventListener("popstate", () => {
        this.track("route_change", { path: window.location.pathname });
      });

      console.info("[EduEagle Analytics] Institutional telemetry initialized.");
    }
  };

  window.EagleAnalytics = EagleAnalytics;
  document.addEventListener("DOMContentLoaded", function () {
    EagleAnalytics.init();
  });
})();

