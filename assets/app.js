// assets/app.js

const sidebar =
  document.getElementById("sidebar");

const overlay =
  document.getElementById("overlay");

const menuToggle =
  document.getElementById("menuToggle");

menuToggle?.addEventListener("click", () => {

  sidebar.classList.toggle("open");

  overlay.classList.toggle("show");

});

overlay?.addEventListener("click", () => {

  sidebar.classList.remove("open");

  overlay.classList.remove("show");

});

const themeToggle =
  document.getElementById("themeToggle");

function applyTheme(theme) {

  if (theme === "light") {
    document.body.classList.add("light");
  } else {
    document.body.classList.remove("light");
  }
}

const storedTheme =
  localStorage.getItem("theme");

if (storedTheme) {

  applyTheme(storedTheme);

} else {

  const prefersLight =
    window.matchMedia(
      "(prefers-color-scheme: light)"
    ).matches;

  applyTheme(prefersLight ? "light" : "dark");
}

themeToggle?.addEventListener("click", () => {

  const current =
    document.body.classList.contains("light")
      ? "light"
      : "dark";

  const next =
    current === "light"
      ? "dark"
      : "light";

  applyTheme(next);

  localStorage.setItem("theme", next);

});

async function loadArticles() {

  try {

    const res =
      await fetch("search-index.json");

    const data =
      await res.json();

    const list =
      document.getElementById("articleList");

    const search =
      document.getElementById("searchInput");

    function render(items) {

      list.innerHTML = "";

      items.forEach(item => {

        const a =
          document.createElement("a");

        a.href = item.file;

        a.innerText = item.title;

        list.appendChild(a);

      });

    }

    render(data);

    search?.addEventListener("input", () => {

      const q =
        search.value.toLowerCase();

      const filtered =
        data.filter(item => {

          return (
            item.title.toLowerCase().includes(q) ||
            item.text.toLowerCase().includes(q)
          );

        });

      render(filtered);

    });

  } catch (err) {

    console.error(err);

  }
}

loadArticles();

if ("serviceWorker" in navigator) {

  navigator.serviceWorker.register("sw.js");

}
