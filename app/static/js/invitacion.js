/* Invitación: apertura del sobre, revelados al scroll y micro-interacciones.
   Todo con transform/opacity para que ande fluido en teléfonos. */
(function () {
  "use strict";

  var quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var pagina = document.getElementById("pagina");

  // Si algo falla, nada queda invisible: se muestra todo sin animación.
  function revelarTodo() {
    var ocultos = document.querySelectorAll("[data-reveal],[data-reveal-grupo] > *");
    Array.prototype.forEach.call(ocultos, function (el) { el.classList.add("visible"); });
    var caja = document.getElementById("sobre");
    if (caja) caja.remove();
    if (pagina) pagina.classList.remove("oculta");
    document.body.style.overflow = "";
  }
  window.addEventListener("error", revelarTodo);

  /* ------------------------------------------------------------------ sobre */
  function abrirPagina() {
    if (!pagina) return;
    pagina.classList.remove("oculta");
    document.body.style.overflow = "";
    document.body.classList.add("listo");
    arrancarRevelados();
  }

  (function sobre() {
    var caja = document.getElementById("sobre");
    var sello = document.getElementById("abrir-sobre");
    if (!caja || !sello || !pagina) {
      abrirPagina();
      return;
    }

    var yaVisto = false;
    try { yaVisto = sessionStorage.getItem("sobre-abierto") === "1"; } catch (e) {}

    if (yaVisto || location.hash) {
      caja.remove();
      abrirPagina();
      return;
    }

    pagina.classList.add("oculta");
    document.body.style.overflow = "hidden";

    function abrir() {
      sello.removeEventListener("click", abrir);
      try { sessionStorage.setItem("sobre-abierto", "1"); } catch (e) {}

      if (quieto) {
        caja.classList.add("sobre--abierto");
        setTimeout(function () { caja.remove(); abrirPagina(); }, 300);
        return;
      }

      caja.classList.add("abriendo");                                   // solapa se abre
      setTimeout(function () { caja.classList.add("sacando"); }, 700);   // carta sale
      setTimeout(function () { caja.classList.add("saliendo"); }, 1950); // sobre se apaga
      setTimeout(function () {
        caja.classList.add("sobre--abierto");                            // velo crema se va
        abrirPagina();
      }, 2600);
      setTimeout(function () { caja.remove(); }, 3600);
    }

    sello.addEventListener("click", abrir);
    caja.addEventListener("click", function (e) { if (e.target === caja) abrir(); });
  })();

  /* ------------------------------------------------- revelados al hacer scroll */
  var observador = null;

  function arrancarRevelados() {
    var sueltos = Array.prototype.slice.call(document.querySelectorAll("[data-reveal]"));
    var grupos = Array.prototype.slice.call(document.querySelectorAll("[data-reveal-grupo]"));
    var hijos = [];

    grupos.forEach(function (grupo) {
      Array.prototype.slice.call(grupo.children).forEach(function (hijo, i) {
        hijo.dataset.delay = String(i * 110);
        hijos.push(hijo);
      });
    });

    var todos = sueltos.concat(hijos);

    if (quieto || !("IntersectionObserver" in window)) {
      todos.forEach(function (el) { el.classList.add("visible"); });
      var lista = document.querySelector(".linea-tiempo");
      if (lista) lista.classList.add("pintada");
      return;
    }

    observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (entrada) {
        if (!entrada.isIntersecting) return;
        var el = entrada.target;
        var espera = parseInt(el.dataset.delay || "0", 10);
        setTimeout(function () { el.classList.add("visible"); }, espera);
        observador.unobserve(el);
      });
    }, { threshold: 0.15, rootMargin: "0px 0px -8% 0px" });

    todos.forEach(function (el) { observador.observe(el); });

    // la línea del itinerario se dibuja cuando la sección entra
    var lista = document.querySelector(".linea-tiempo");
    if (lista) {
      var obsLinea = new IntersectionObserver(function (entradas) {
        entradas.forEach(function (e) {
          if (e.isIntersecting) { lista.classList.add("pintada"); obsLinea.disconnect(); }
        });
      }, { threshold: 0.2 });
      obsLinea.observe(lista);
    }
  }

  /* --------------------------------------------------------------- countdown */
  (function countdown() {
    var caja = document.getElementById("cuenta");
    if (!caja) return;
    var objetivo = new Date(caja.dataset.fecha).getTime();
    var campos = {
      dias: caja.querySelector('[data-u="dias"]'),
      horas: caja.querySelector('[data-u="horas"]'),
      min: caja.querySelector('[data-u="min"]'),
      seg: caja.querySelector('[data-u="seg"]')
    };

    function pad(n) { return String(n).padStart(2, "0"); }

    function poner(campo, valor) {
      if (!campo || campo.textContent === valor) return;
      campo.textContent = valor;
      if (quieto) return;
      campo.classList.remove("tic");
      void campo.offsetWidth;          // reinicia la animación
      campo.classList.add("tic");
    }

    function tick() {
      var falta = objetivo - Date.now();
      if (falta < 0) falta = 0;
      var seg = Math.floor(falta / 1000);
      poner(campos.dias, String(Math.floor(seg / 86400)));
      poner(campos.horas, pad(Math.floor((seg % 86400) / 3600)));
      poner(campos.min, pad(Math.floor((seg % 3600) / 60)));
      poner(campos.seg, pad(seg % 60));
    }
    tick();
    setInterval(tick, 1000);
  })();

  /* ------------------------------ progreso de lectura, barra flotante, parallax */
  (function scroll() {
    var barraProgreso = document.getElementById("progreso");
    var mini = document.getElementById("mini-barra");
    var hero = document.querySelector(".hero");
    var marco = document.querySelector("[data-parallax]");
    var factor = marco ? parseFloat(marco.dataset.parallax) : 0;
    var pendiente = false;

    function pintar() {
      pendiente = false;
      var alto = document.documentElement.scrollHeight - window.innerHeight;
      var y = window.scrollY;

      if (barraProgreso && alto > 0) {
        barraProgreso.style.width = Math.min(100, (y / alto) * 100) + "%";
      }
      if (mini && hero) {
        mini.classList.toggle("visible", y > hero.offsetHeight * 0.75);
      }
      if (marco && !quieto && y < window.innerHeight * 1.2) {
        marco.style.transform = "translateY(" + (y * factor).toFixed(1) + "px)";
        marco.style.opacity = String(Math.max(0, 1 - (y / (window.innerHeight * 0.9))));
      }
    }

    window.addEventListener("scroll", function () {
      if (pendiente) return;
      pendiente = true;
      window.requestAnimationFrame(pintar);
    }, { passive: true });
    pintar();
  })();

  /* -------------------------------------------------------- alias copiable */
  (function alias() {
    var valor = document.getElementById("alias");
    var aviso = document.getElementById("alias-aviso");
    if (!valor) return;
    valor.addEventListener("click", function () {
      var texto = valor.dataset.copiar || valor.textContent;
      var mostrar = function () {
        if (!aviso) return;
        aviso.classList.add("visible");
        setTimeout(function () { aviso.classList.remove("visible"); }, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(texto).then(mostrar, function () {});
      } else {
        var tmp = document.createElement("textarea");
        tmp.value = texto;
        document.body.appendChild(tmp);
        tmp.select();
        try { document.execCommand("copy"); mostrar(); } catch (e) {}
        document.body.removeChild(tmp);
      }
    });
  })();

  /* ------------------------------------------------ estado del botón de RSVP */
  (function formulario() {
    var form = document.querySelector(".formulario");
    if (!form) return;
    form.addEventListener("submit", function () {
      var boton = form.querySelector('button[type="submit"]');
      if (!boton) return;
      boton.disabled = true;
      boton.textContent = boton.dataset.enviando || "Enviando…";
    });
  })();
})();
