/* Invitación de Boda: Apertura de sobre en 3D con GSAP ScrollTrigger,
   revelados al scroll y micro-interacciones. */
(function () {
  "use strict";

  var quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var pagina = document.getElementById("pagina");

  // Si algo falla, nada queda invisible: se muestra todo sin animación.
  function revelarTodo() {
    var ocultos = document.querySelectorAll("[data-reveal],[data-reveal-grupo] > *");
    Array.prototype.forEach.call(ocultos, function (el) { el.classList.add("visible"); });
    var wrapper = document.getElementById("envelope-pin-wrapper");
    if (wrapper) wrapper.style.display = "none";
    document.body.style.overflow = "";
  }
  window.addEventListener("error", revelarTodo);

  /* ------------------------------------------------ GSAP Envelope 25-Frame Canvas Sequence & Green Flash Filter */
  /* ------------------------------------------------ Sobre Interactivo: Apertura con Video y Revelado de Tarjeta */
  (function initEnvelope() {
    var wrapper = document.getElementById("envelope-pin-wrapper");
    var stage = document.getElementById("envelope-stage");
    var hint = document.getElementById("envelope-scroll-hint");
    var seal = document.getElementById("wax-seal");
    var flash = document.getElementById("flash-verde");
    var system = document.getElementById("envelope-system");
    var video = document.getElementById("envelope-video");
    var cardContainer = document.getElementById("envelope-card-container");
    var cargando = document.getElementById("envelope-cargando");

    if (!wrapper || !stage || !system || !video) {
      if (wrapper) wrapper.style.display = "none";  // que no quede tapando la pagina sin poder abrirse
      arrancarRevelados();
      return;
    }

    function finalizarApertura() {
      wrapper.style.transition = "opacity 0.75s ease, visibility 0.75s ease";
      wrapper.style.opacity = "0";
      wrapper.style.pointerEvents = "none";
      setTimeout(function () {
        wrapper.style.display = "none";
        document.body.classList.remove("envelope-locked");
        document.body.style.overflow = "";
        arrancarRevelados();
      }, 750);
    }

    // Si navegó directamente a una sección con ancla (#rsvp) o prefiere sin animación:
    if (location.hash || quieto) {
      wrapper.style.display = "none";
      arrancarRevelados();
      return;
    }

    // Bloquear scroll mientras el sobre está cerrado
    document.body.classList.add("envelope-locked");
    document.body.style.overflow = "hidden";

    // Inicializar estado de la tarjeta interior con el texto de la boda
    if (cardContainer) {
      if (window.gsap) {
        gsap.set(cardContainer, {
          xPercent: -50,
          yPercent: -50,
          x: 0,
          y: 0,
          opacity: 0,
          scale: 0.94,
          pointerEvents: "none"
        });
      } else {
        cardContainer.style.opacity = "0";
      }
    }

    // Fallback de seguridad si el video no pudiera cargarse
    video.addEventListener("error", function () {
      console.warn("No se pudo cargar el video del sobre, pasando a modo fallback");
      if (cardContainer) cardContainer.style.opacity = "1";
      marcarListo();  // que igual se pueda seguir: sin esto quedaria "Cargando…" para siempre
    });

    // El video tiene que estar cargado ANTES de dejar tocar el sobre (para que nunca se vea
    // trabado en telefonos de gama baja o con poca señal): mientras carga se ve "Cargando…" en
    // vez de "Tocá para abrir", y como resguardo nunca se espera mas de CARGA_MAXIMA_MS (una
    // conexion muy mala no tiene por que dejar a alguien mirando un cartel para siempre).
    var CARGA_MAXIMA_MS = 8000;
    var listo = false;

    function marcarListo() {
      if (listo) return;
      listo = true;
      if (cargando) cargando.classList.add("oculto");
      if (hint) hint.classList.remove("oculto");
      if (seal) seal.style.cursor = "";
    }

    if (seal) seal.style.cursor = "wait";
    if (video.readyState >= video.HAVE_ENOUGH_DATA) {
      marcarListo();
    } else {
      video.addEventListener("canplaythrough", marcarListo, { once: true });
      setTimeout(marcarListo, CARGA_MAXIMA_MS);
      try { video.load(); } catch (e) { }
    }

    var abriendo = false;
    var abierto = false;
    var allowSkip = false;
    var tl = null;

    function abrirSobre() {
      if (abriendo || abierto) return;
      abriendo = true;
      allowSkip = false;

      // Habilitar salto después de 700ms para evitar toques accidentales
      setTimeout(function () {
        allowSkip = true;
      }, 700);

      // Quitar animación de respiración del sello
      if (seal) {
        seal.style.animation = "none";
        seal.style.cursor = "default";
      }

      // Reproducción inmediata del video con aceleración por hardware
      try {
        video.currentTime = 0;
        var playPromise = video.play();
        if (playPromise !== undefined) {
          playPromise.catch(function (err) {
            console.warn("Reproducción de video diferida:", err);
          });
        }
      } catch (e) {
        console.warn("Excepción al iniciar video:", e);
      }

      if (!window.gsap) {
        if (cardContainer) cardContainer.style.opacity = "1";
        setTimeout(finalizarApertura, 3500);
        return;
      }

      tl = gsap.timeline({
        onComplete: function () {
          abierto = true;
          finalizarApertura();
        }
      });

      // 1. Desvanecer la pista de toque de inmediato
      if (hint) {
        tl.to(hint, {
          opacity: 0,
          scale: 0.9,
          duration: 0.3,
          ease: "power2.out"
        }, 0);
        tl.set(hint, { pointerEvents: "none", display: "none" }, 0.3);
      }

      // 2. Despegar y elevar el sello de cera S&M
      if (seal) {
        tl.to(seal, {
          xPercent: -50,
          yPercent: -50,
          scale: 1.35,
          opacity: 0,
          duration: 0.45,
          ease: "back.in(1.4)"
        }, 0);
        tl.set(seal, { pointerEvents: "none", display: "none" }, 0.45);
      }

      // 3. Revelado del texto de la invitación a partir de 1.5s (cuando el sobre ya abrió su interior)
      if (cardContainer) {
        tl.fromTo(cardContainer, {
          opacity: 0,
          scale: 0.95,
          xPercent: -50,
          yPercent: -50,
          x: 0,
          y: 0
        }, {
          opacity: 1,
          scale: 1,
          xPercent: -50,
          yPercent: -50,
          x: 0,
          y: 0,
          duration: 0.65,
          ease: "power2.out"
        }, 1.72);
      }

      // 4. Destello etéreo dorado al completarse la apertura (2.05s a 2.35s)
      if (flash) {
        tl.fromTo(flash, { opacity: 0, scale: 0.98 }, {
          opacity: 0.55,
          scale: 1.02,
          duration: 0.25,
          ease: "power2.in"
        }, 2.05);
        tl.to(flash, {
          opacity: 0,
          scale: 1,
          duration: 0.35,
          ease: "power2.out"
        }, 2.3);
      }

      // 5. Al terminar el video (~2.4s), pausar en el último fotograma
      tl.add(function () {
        if (video) {
          try { video.pause(); } catch (err) { }
        }
      }, 2.4);

      // Pausa para que los invitados lean con calma el texto de la invitación (+2.7s)
      tl.to({}, { duration: 2.7 });
    }

    function alTocar(e) {
      if (!listo) return;  // el video todavia esta cargando: no dejar abrir a los tirones
      if (e && e.stopPropagation) {
        e.stopPropagation();
      }
      try {
        if (window.getSelection) {
          window.getSelection().removeAllRanges();
        }
      } catch (err) { }
      if (!abriendo) {
        abrirSobre();
      } else if (!abierto && allowSkip && tl) {
        if (video) {
          try {
            video.currentTime = video.duration || 2.4;
            video.pause();
          } catch (err) { }
        }
        tl.progress(1);
      }
    }

    // Permitir abrir tocando el sello S&M, el sobre o el fondo del escenario
    if (seal) {
      seal.addEventListener("click", alTocar);
      seal.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          alTocar(e);
        }
      });
    }
    if (hint) hint.addEventListener("click", alTocar);
    if (system) system.addEventListener("click", alTocar);
    if (stage) stage.addEventListener("click", alTocar);
    wrapper.addEventListener("click", alTocar);
  })();

  /* ------------------------------------------------ Reproductor de Música ("DALE PLAY...") */
  (function initMusicPlayer() {
    var playerCard = document.querySelector(".music-card, .music-card-minimal");
    var audio = document.getElementById("audio-cancion");
    var btnPlay = document.getElementById("btn-play");
    var btnPrev = document.getElementById("btn-prev");
    var btnNext = document.getElementById("btn-next");
    if (!playerCard || !audio || !btnPlay) return;

    function togglePlay() {
      if (audio.paused) {
        audio.play().then(function () {
          playerCard.classList.add("is-playing");
        }).catch(function () {
          playerCard.classList.add("is-playing");
        });
      } else {
        audio.pause();
        playerCard.classList.remove("is-playing");
      }
    }

    btnPlay.addEventListener("click", togglePlay);

    if (btnPrev) {
      btnPrev.addEventListener("click", function () {
        audio.currentTime = 0;
        if (audio.paused) togglePlay();
      });
    }

    if (btnNext) {
      btnNext.addEventListener("click", function () {
        audio.currentTime = 0;
        if (audio.paused) togglePlay();
      });
    }

    audio.addEventListener("ended", function () {
      playerCard.classList.remove("is-playing");
    });
  })();

  /* ------------------------------------------------- revelados al hacer scroll */
  var observador = null;
  var reveladosArrancados = false;

  function arrancarRevelados() {
    if (reveladosArrancados) return;
    reveladosArrancados = true;
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
    var pistaAbajo = document.getElementById("scroll-abajo");
    var pistaAbajoOculta = false;
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
        mini.classList.toggle("visible", hero.getBoundingClientRect().bottom < 80);
      }
      // El cartel de "seguí bajando" se muestra al entrar (el sobre lo tapa mientras esta
      // cerrado) y desaparece en cuanto la persona empieza a scrollear, sin volver a mostrarse.
      if (pistaAbajo && !pistaAbajoOculta && y > 24) {
        pistaAbajoOculta = true;
        pistaAbajo.classList.add("oculto");
      }
      if (marco && !quieto && hero) {
        var rect = hero.getBoundingClientRect();
        if (rect.top <= window.innerHeight && rect.bottom >= 0) {
          var relY = window.innerHeight - rect.top;
          marco.style.transform = "translateY(" + (relY * factor * 0.4).toFixed(1) + "px)";
        }
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
    var btn = document.getElementById("btn-copiar-alias");
    if (!valor) return;

    function copiar() {
      var texto = valor.dataset.copiar || valor.textContent;
      var mostrar = function () {
        if (!aviso) return;
        aviso.classList.add("visible");
        setTimeout(function () { aviso.classList.remove("visible"); }, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(texto).then(mostrar, function () { });
      } else {
        var tmp = document.createElement("textarea");
        tmp.value = texto;
        document.body.appendChild(tmp);
        tmp.select();
        try { document.execCommand("copy"); mostrar(); } catch (e) { }
        document.body.removeChild(tmp);
      }
    }

    valor.addEventListener("click", copiar);
    if (btn) btn.addEventListener("click", copiar);
  })();

  /* ------------------------------------------------ estado del botón de RSVP */
  (function formulario() {
    var form = document.querySelector(".formulario");
    if (!form) return;
    // El nombre es obligatorio solo para quien asiste (el backend valida lo mismo).
    form.querySelectorAll("select[data-asistencia]").forEach(function (select) {
      var caja = select.closest("fieldset");
      var nombre = caja && caja.querySelector("input[data-nombre-invitado]");
      if (!nombre) return;
      function sincronizar() { nombre.required = select.value === "si"; }
      select.addEventListener("change", sincronizar);
      sincronizar();
    });
    form.addEventListener("submit", function () {
      var boton = form.querySelector('button[type="submit"]');
      if (!boton) return;
      boton.disabled = true;
      boton.textContent = boton.dataset.enviando || "Enviando…";
    });
  })();

  /* ------------------------------------------------ desplazamiento suave para anclas */
  (function anclas() {
    document.querySelectorAll('a[href^="#"]').forEach(function (enlace) {
      enlace.addEventListener("click", function (e) {
        var destinoId = this.getAttribute("href");
        if (destinoId && destinoId.length > 1) {
          var el = document.querySelector(destinoId);
          if (el) {
            e.preventDefault();
            el.scrollIntoView({ behavior: "smooth" });
          }
        }
      });
    });
  })();
})();
