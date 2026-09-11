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
  /* ------------------------------------------------ Sobre Interactivo: Apertura al Tocar */
  (function initEnvelope() {
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

    // 83 Fotogramas progresivos con movimiento continuo real
    var FRAME_NUMBERS = [
      1, 13, 15, 16, 17, 18, 19, 21, 22, 23, 24, 25, 27, 28, 29, 30,
      31, 34, 35, 36, 37, 39, 40, 41, 42, 43, 45, 46, 47, 48, 49, 51,
      52, 53, 54, 55, 57, 58, 59, 60, 61, 64, 65, 66, 67, 69, 70, 71,
      72, 73, 75, 76, 77, 78, 79, 81, 82, 83, 84, 85, 87, 88, 89, 90,
      91, 94, 95, 96, 97, 99, 100, 101, 102, 103, 105, 106, 107, 108,
      109, 111, 113, 114, 115
    ];
    var TOTAL_FRAMES = FRAME_NUMBERS.length;
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

        // Mezcla suave continua entre fotogramas para 60fps
        if (frac > 0.02 && imgB && imgB.complete && imgB.naturalWidth > 0) {
          ctx.globalAlpha = frac;
          ctx.drawImage(imgB, 0, 0, canvas.width, canvas.height);
        }
      }
    }

    for (var i = 0; i < TOTAL_FRAMES; i++) {
      (function (index) {
        var num = FRAME_NUMBERS[index];
        var img = new Image();
        img.src = "/static/img/seq/frame_" + pad(num, 3) + ".jpg";
        img.onload = function () {
          loadedCount++;
          if (index === 0) {
            renderCanvasFrame(0);
          }
        };
        frameImages.push(img);
      })(i);
    }

    if (frameImages[0] && frameImages[0].complete && frameImages[0].naturalWidth > 0) {
      renderCanvasFrame(0);
    }

    // Inicializar estado de la tarjeta interior
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

    var abriendo = false;
    var abierto = false;
    var allowSkip = false;
    var tl = null;

    function abrirSobre() {
      if (abriendo || abierto) return;
      abriendo = true;
      allowSkip = false;

      // Habilitar salto sólo después de 700ms para evitar falsos toques durante la interacción inicial
      setTimeout(function () {
        allowSkip = true;
      }, 700);

      // Quitar animación de respiración del sello
      if (seal) {
        seal.style.animation = "none";
        seal.style.cursor = "default";
      }

      if (!window.gsap) {
        finalizarApertura();
        return;
      }

      var frameState = { frame: 0 };

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

      // 3. Secuencia continua de apertura del sobre verde (2.3 segundos cinematográficos)
      tl.to(frameState, {
        frame: TOTAL_FRAMES - 1,
        duration: 2.3,
        ease: "power1.inOut",
        onUpdate: function () {
          renderCanvasFrame(frameState.frame);
        }
      }, 0.15);

      // 4. Revelado natural de la carta en el interior
      if (cardContainer) {
        tl.fromTo(cardContainer, {
          opacity: 0,
          scale: 0.94,
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
          duration: 0.7,
          ease: "power2.out"
        }, 1.35);
      }

      // 5. Destello verde etéreo al completarse la apertura
      if (flash) {
        tl.fromTo(flash, { opacity: 0, scale: 0.98 }, {
          opacity: 0.55,
          scale: 1.02,
          duration: 0.25,
          ease: "power2.in"
        }, 1.95);
        tl.to(flash, {
          opacity: 0,
          scale: 1,
          duration: 0.35,
          ease: "power2.out"
        }, 2.2);
      }

      // Pausa prolongada para que los invitados puedan leer la tarjeta con calma antes de pasar a la invitación (+2s)
      tl.to({}, { duration: 2.7 });
    }

    function alTocar(e) {
      if (e && e.stopPropagation) {
        e.stopPropagation();
      }
      try {
        if (window.getSelection) {
          window.getSelection().removeAllRanges();
        }
      } catch (err) {}
      if (!abriendo) {
        abrirSobre();
      } else if (!abierto && allowSkip && tl) {
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

    window.addEventListener("load", function () {
      renderCanvasFrame(0);
    });
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
