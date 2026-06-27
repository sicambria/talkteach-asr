<script>
  // A cheerful mascot placeholder. Swap the emoji for real art later.
  // jargon-free: just a friendly face that reacts with different "moods".
  export let mood = "happy"; // happy | wave | think | cheer | oops
  export let size = 96;

  const FACES = {
    happy: "🤖",
    wave: "👋",
    think: "🤔",
    cheer: "🎉",
    oops: "😅",
  };

  $: face = FACES[mood] || FACES.happy;
</script>

<span
  class="mascot"
  style="font-size:{size}px;line-height:1;"
  role="img"
  aria-label="friendly helper"
>
  {face}
</span>

<style>
  .mascot {
    display: inline-block;
    animation: bob 2.4s ease-in-out infinite;
  }

  @keyframes bob {
    0%,
    100% {
      transform: translateY(0) rotate(-2deg);
    }
    50% {
      transform: translateY(-6px) rotate(2deg);
    }
  }
</style>
