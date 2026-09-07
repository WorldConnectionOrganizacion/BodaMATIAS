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
  (function initGSAPEnvelope() {
    var wrapper = document.getElementById("envelope-pin-wrapper");
    var stage = document.getElementById("envelope-stage");
    var hint = document.getElementById("envelope-scroll-hint");
    var seal = document.getElementById("wax-seal");
    var flash = document.getElementById("flash-verde");
    var system = document.getElementById("envelope-system");
    var canvas = document.getElementById("envelope-canvas");
    var cardContainer = document.getElementById("envelope-card-container");

    if (!wrapper || !stage || !system || !canvas) {
      arrancarRevelados();
      return;
    }

    var ctx = canvas.getContext("2d");

    // Si el usuario navegó a un ancla directa (#rsvp) o prefiere sin movimiento
    if (location.hash || quieto) {
      wrapper.style.display = "none";
      arrancarRevelados();
      return;
    }

    // Evitar que el navegador restaure una posición de scroll previa al navegar entre invitaciones
    if ("scrollRestoration" in history && !location.hash) {
      history.scrollRestoration = "manual";
      window.scrollTo(0, 0);
    }

    // 116 Fotogramas de alta definición extraídos del video
    var TOTAL_FRAMES = 116;
    var frameImages = [];
    var loadedCount = 0;

    function pad(n, width) {
      var s = String(n);
      while (s.length < width) s = "0" + s;
      return s;
    }

    function renderCanvasFrame(virtualFrame) {
      if (!canvas || !ctx) return;
      var clamped = Math.max(0, Math.min(TOTAL_FRAMES - 1, virtualFrame));
      var idxA = Math.floor(clamped);
      var idxB = Math.min(TOTAL_FRAMES - 1, idxA + 1);
      var frac = clamped - idxA;

      var imgA = frameImages[idxA];
      var imgB = frameImages[idxB];

      if (imgA && imgA.complete && imgA.naturalWidth > 0) {
        ctx.globalAlpha = 1.0;
        ctx.drawImage(imgA, 0, 0, canvas.width, canvas.height);

        // Mezcla continua entre fotogramas para lograr 60fps sin sensación de saltos
        if (frac > 0.02 && imgB && imgB.complete && imgB.naturalWidth > 0) {
          ctx.globalAlpha = frac;
          ctx.drawImage(imgB, 0, 0, canvas.width, canvas.height);
        }
      }
    }

    for (var i = 1; i <= TOTAL_FRAMES; i++) {
      (function (index) {
        var img = new Image();
        img.src = "/static/img/seq/frame_" + pad(index + 1, 3) + ".jpg";
        img.onload = function () {
          loadedCount++;
          if (index === 0) {
            renderCanvasFrame(0);
          }
        };
        frameImages.push(img);
      })(i - 1);
    }

    if (window.gsap && window.ScrollTrigger) {
      gsap.registerPlugin(ScrollTrigger);

      var scrollDist = 2600;
      var frameState = { frame: 0 };

      if (cardContainer) {
        gsap.set(cardContainer, {
          xPercent: -50,
          yPercent: -50,
          x: 0,
          y: 0,
          opacity: 0,
          scale: 0.95,
          pointerEvents: "none"
        });
      }

      var tl = gsap.timeline({
        scrollTrigger: {
          trigger: wrapper,
          start: "top top",
          end: "+=" + scrollDist,
          pin: true,
          scrub: 0.6,
          anticipatePin: 1,
          onUpdate: function (self) {
            if (self.progress > 0.75) {
              arrancarRevelados();
            }
          }
        }
      });

      // 1. Pista de scroll se desvanece suavemente al inicio (0.00 -> 0.06)
      tl.to(hint, {
        opacity: 0,
        y: 18,
        ease: "power1.out",
        duration: 0.06
      }, 0);

      // 2. El sello circular crema S&M en el centro se despega y desvanece de forma natural (0.01 -> 0.12)
      if (seal) {
        gsap.set(seal, { xPercent: -50, yPercent: -50 });
        tl.to(seal, {
          scale: 1.2,
          opacity: 0,
          ease: "power1.out",
          duration: 0.11
        }, 0.01);
      }

      // 3. Secuencia de fotogramas fluida: del fotograma 0 al 115 (0.04 -> 0.88)
      // Solapa izquierda -> Solapa derecha -> Solapa superior e inferior -> Revelado interior
      tl.to(frameState, {
        frame: TOTAL_FRAMES - 1,
        ease: "none",
        duration: 0.84,
        onUpdate: function () {
          renderCanvasFrame(frameState.frame);
        }
      }, 0.04);

      // 4. Revelado natural del texto de invitación impreso en el interior del sobre (0.60 -> 0.82)
      if (cardContainer) {
        // A medida que las solapas superior e inferior se abren y descubren el papel interior,
        // la caligrafía/impresión sobre el sobre se revela con nitidez y elegancia.
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
          ease: "power2.out",
          duration: 0.22
        }, 0.60);

        // Habilitar interacción con los elementos al completarse la apertura
        tl.set(cardContainer, { pointerEvents: "auto" }, 0.82);
      }

      // 5. Destello verde etéreo / resplandor suave de apertura (0.80 -> 0.88 -> 0.95)
      if (flash) {
        tl.fromTo(flash, {
          opacity: 0,
          scale: 0.98
        }, {
          opacity: 0.65,
          scale: 1.02,
          ease: "power2.in",
          duration: 0.08
        }, 0.80);

        tl.to(flash, {
          opacity: 0,
          scale: 1,
          ease: "power2.out",
          duration: 0.08
        }, 0.88);
      }

      // Click / Tap para abrir automáticamente de forma fluida
      function abrirClick() {
        var top = wrapper.offsetTop + scrollDist * 0.98;
        window.scrollTo({ top: top, behavior: "smooth" });
      }

      if (seal) seal.addEventListener("click", abrirClick);
      if (system) system.addEventListener("click", abrirClick);
      if (hint) hint.addEventListener("click", abrirClick);

      window.addEventListener("load", function () {
        ScrollTrigger.refresh();
        renderCanvasFrame(frameState.frame);
      });
    } else {
      arrancarRevelados();
    }
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
        mini.classList.toggle("visible", hero.getBoundingClientRect().bottom < 80);
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
        navigator.clipboard.writeText(texto).then(mostrar, function () {});
      } else {
        var tmp = document.createElement("textarea");
        tmp.value = texto;
        document.body.appendChild(tmp);
        tmp.select();
        try { document.execCommand("copy"); mostrar(); } catch (e) {}
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
    form.addEventListener("submit", function () {
      var boton = form.querySelector('button[type="submit"]');
      if (!boton) return;
      boton.disabled = true;
      boton.textContent = boton.dataset.enviando || "Enviando…";
    });
  })();
})();
