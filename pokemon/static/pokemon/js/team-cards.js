(() => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const tiltProps = ['--rx', '--ry', '--mx', '--my', '--glare'];
  const ease = 'cubic-bezier(.2, .8, .2, 1)';

  const resetTilt = (el) => {
    el.classList.remove('is-tilting');
    tiltProps.forEach((prop) => el.style.removeProperty(prop));
  };

  // Pointer-events en maten komen van een niet-getransformeerde wrapper: meten op het
  // kantelende element zelf laat de rand meebewegen en geeft jitter/flikkeren aan de randen.
  const bindTilt = (el) => {
    if (reduceMotion) return;
    const area = el.closest('[data-tcg-tilt-area]') ?? el;
    let frame = null;
    let rect = null;

    const onEnter = (event) => {
      if (event.pointerType === 'touch') return;
      rect = area.getBoundingClientRect();
      el.style.setProperty('--tcg-perspective', `${Math.round(rect.width * 2.5)}px`);
      el.classList.add('is-tilting');
    };

    const onMove = (event) => {
      if (event.pointerType === 'touch') return;
      if (!rect) onEnter(event);
      const x = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1);
      const y = Math.min(Math.max((event.clientY - rect.top) / rect.height, 0), 1);

      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        el.style.setProperty('--rx', `${(0.5 - y) * 12}deg`);
        el.style.setProperty('--ry', `${(x - 0.5) * 16}deg`);
        el.style.setProperty('--mx', `${x * 100}%`);
        el.style.setProperty('--my', `${y * 100}%`);
        el.style.setProperty('--glare', '1');
      });
    };

    const onLeave = () => {
      cancelAnimationFrame(frame);
      rect = null;
      resetTilt(el);
    };

    const onScroll = () => { rect = null; };

    area.addEventListener('pointerenter', onEnter);
    area.addEventListener('pointermove', onMove);
    area.addEventListener('pointerleave', onLeave);
    window.addEventListener('scroll', onScroll, { passive: true, capture: true });

    return () => {
      onLeave();
      area.removeEventListener('pointerenter', onEnter);
      area.removeEventListener('pointermove', onMove);
      area.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('scroll', onScroll, { capture: true });
    };
  };

  document.querySelectorAll('[data-tcg-tilt]').forEach(bindTilt);

  /* Teamlid-modal */
  const modal = document.getElementById('team-modal');
  if (!modal) return;

  const backdrop = modal.querySelector('.team-modal-backdrop');
  const inner = modal.querySelector('.team-modal-inner');
  const cardHost = modal.querySelector('.team-modal-card');
  const infoHost = modal.querySelector('.team-modal-info');
  const controls = modal.querySelector('.team-modal-controls');
  const prevButton = modal.querySelector('[data-team-prev]');
  const nextButton = modal.querySelector('[data-team-next]');
  const slots = [...document.querySelectorAll('[data-team-open]')];

  let current = null;
  let busy = false;
  let unbindCloneTilt = null;

  const slabOf = (index) => slots[index].querySelector('.tcg-slab');
  const animate = (el, keyframes, options) => (
    reduceMotion ? Promise.resolve() : el.animate(keyframes, { easing: ease, fill: 'both', ...options }).finished
  );
  const clearAnimations = (...els) => els.forEach((el) => el.getAnimations().forEach((a) => a.cancel()));

  // Keyframe die een element op `to` visueel op de plek van `from` zet.
  const flipFrom = (from, to) => ({
    transformOrigin: 'top left',
    transform: `translate(${from.left - to.left}px, ${from.top - to.top}px) scale(${from.width / to.width})`,
  });
  const flipRest = { transformOrigin: 'top left', transform: 'none' };

  const fill = (index) => {
    const slug = slots[index].dataset.teamOpen;
    const source = slabOf(index);
    resetTilt(source);

    unbindCloneTilt?.();
    const clone = source.cloneNode(true);
    cardHost.replaceChildren(clone);
    unbindCloneTilt = bindTilt(clone);

    infoHost.replaceChildren(document.getElementById(`team-lid-${slug}`).content.cloneNode(true));
    prevButton.hidden = index === 0;
    nextButton.hidden = index === slots.length - 1;
    if (document.activeElement?.hidden) {
      (prevButton.hidden ? nextButton : prevButton).focus();
    }
    modal.scrollTop = 0;
    current = index;
    history.replaceState(null, '', `#${slug}`);
    return clone;
  };

  const open = async (index, fromGrid = true) => {
    if (busy || current !== null) return;
    busy = true;

    const clone = fill(index);
    document.documentElement.classList.add('team-modal-open');
    modal.showModal();

    const source = slabOf(index);
    const from = source.getBoundingClientRect();
    const to = clone.getBoundingClientRect();
    source.style.visibility = 'hidden';

    await Promise.all([
      animate(backdrop, [{ opacity: 0 }, { opacity: 1 }], { duration: 400 }),
      animate(controls, [{ opacity: 0 }, { opacity: 1 }], { duration: 300, delay: 350 }),
      fromGrid
        ? animate(clone, [flipFrom(from, to), flipRest], { duration: 700 })
        : animate(clone, [{ opacity: 0, transform: 'translateY(40px) scale(.95)' }, { opacity: 1, transform: 'none' }], { duration: 500 }),
      animate(infoHost, [{ opacity: 0, transform: 'translateX(48px)' }, { opacity: 1, transform: 'none' }], { duration: 550, delay: 250 }),
    ]);

    clearAnimations(clone, infoHost, backdrop, controls);
    busy = false;
  };

  const close = async () => {
    if (busy || current === null) return;
    busy = true;

    const source = slabOf(current);
    const clone = cardHost.firstElementChild;
    unbindCloneTilt?.();
    unbindCloneTilt = null;

    const sourceRect = source.getBoundingClientRect();
    if (sourceRect.bottom < 0 || sourceRect.top > window.innerHeight) {
      source.scrollIntoView({ block: 'center', behavior: 'instant' });
    }
    const from = source.getBoundingClientRect();
    const to = clone.getBoundingClientRect();

    await Promise.all([
      animate(controls, [{ opacity: 1 }, { opacity: 0 }], { duration: 200 }),
      animate(infoHost, [{ opacity: 1 }, { opacity: 0 }], { duration: 300 }),
      animate(clone, [flipRest, flipFrom(from, to)], { duration: 600, delay: 100 }),
      animate(backdrop, [{ opacity: 1 }, { opacity: 0 }], { duration: 500, delay: 150 }),
    ]);

    source.style.visibility = '';
    modal.close();
  };

  const go = async (direction) => {
    const target = current + direction;
    if (busy || current === null || target < 0 || target >= slots.length) return;
    busy = true;

    // Kaart draait om haar verticale as tot ze op haar kant staat; de volgende draait verder in.
    const turn = (deg) => `perspective(1600px) translateX(${deg / -6}px) rotateY(${deg}deg) scale(${1 - Math.abs(deg) / 1500})`;
    const slide = (sign) => `translateX(${sign * 24}px)`;

    await Promise.all([
      animate(cardHost.firstElementChild, [{ transform: turn(0) }, { transform: turn(90 * direction) }], { duration: 240, easing: 'cubic-bezier(.5, 0, .9, .5)' }),
      animate(infoHost, [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: slide(-direction) }], { duration: 220, easing: 'ease-in' }),
    ]);

    slabOf(current).style.visibility = '';
    clearAnimations(infoHost);
    const clone = fill(target);
    slabOf(target).style.visibility = 'hidden';

    await Promise.all([
      animate(clone, [{ transform: turn(-90 * direction) }, { transform: turn(0) }], { duration: 420, easing: 'cubic-bezier(.15, .6, .3, 1)' }),
      animate(infoHost, [{ opacity: 0, transform: slide(direction) }, { opacity: 1, transform: 'none' }], { duration: 420, delay: 60 }),
    ]);

    clearAnimations(clone, infoHost);
    busy = false;
  };

  slots.forEach((slot, index) => {
    slot.addEventListener('click', (event) => {
      event.preventDefault();
      open(index);
    });
  });

  modal.querySelector('[data-team-close]').addEventListener('click', close);
  prevButton.addEventListener('click', () => go(-1));
  nextButton.addEventListener('click', () => go(1));

  modal.addEventListener('click', (event) => {
    if (event.target === inner || event.target === backdrop || event.target === modal) close();
  });

  modal.addEventListener('cancel', (event) => {
    event.preventDefault();
    close();
  });

  document.addEventListener('keydown', (event) => {
    if (!modal.open) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      close();
    }
    if (event.key === 'ArrowLeft') go(-1);
    if (event.key === 'ArrowRight') go(1);
  });

  modal.addEventListener('close', () => {
    const slot = current !== null ? slots[current] : null;
    if (slot) slabOf(current).style.visibility = '';
    clearAnimations(backdrop, controls, infoHost);
    unbindCloneTilt?.();
    unbindCloneTilt = null;
    cardHost.replaceChildren();
    infoHost.replaceChildren();
    document.documentElement.classList.remove('team-modal-open');
    history.replaceState(null, '', window.location.pathname + window.location.search);
    current = null;
    busy = false;
    slot?.focus({ preventScroll: true });
  });

  const initial = slots.findIndex((slot) => `#${slot.dataset.teamOpen}` === decodeURIComponent(window.location.hash));
  if (initial > -1) open(initial, false);
})();
