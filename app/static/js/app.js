document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
  const sidebarOverlay = document.querySelector("[data-sidebar-overlay]");
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const sidebarLinks = document.querySelectorAll(".nav-link");
  const notifToggle = document.querySelector("[data-notif-toggle]");
  const notifMenu = document.querySelector("[data-notif-menu]");

  const savedTheme = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", savedTheme);

  const setTheme = (theme) => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  };

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "dark";
      setTheme(current === "dark" ? "light" : "dark");
    });
  }

  if (sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
      body.classList.toggle("sidebar-open");
    });
  }

  if (sidebarOverlay) {
    sidebarOverlay.addEventListener("click", () => {
      body.classList.remove("sidebar-open");
    });
  }

  if (notifToggle && notifMenu) {
    notifToggle.addEventListener("click", (event) => {
      event.stopPropagation();
      notifMenu.classList.toggle("open");
    });

    notifMenu.addEventListener("click", (event) => {
      event.stopPropagation();
    });

    document.addEventListener("click", () => {
      notifMenu.classList.remove("open");
    });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      body.classList.remove("sidebar-open");
      if (notifMenu) notifMenu.classList.remove("open");
    }
  });

  const currentPath = window.location.pathname.replace(/\/$/, "");
  sidebarLinks.forEach((link) => {
    const linkPath = new URL(link.href).pathname.replace(/\/$/, "");
    if (linkPath === currentPath || (currentPath && currentPath.startsWith(linkPath) && linkPath !== "/")) {
      link.classList.add("active");
    }
  });

  const toasts = document.querySelectorAll(".toast");
  toasts.forEach((toast) => {
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-8px)";
      toast.style.pointerEvents = "none";
    }, 3000);

    setTimeout(() => {
      toast.remove();
    }, 3400);
  });
});