document.addEventListener('DOMContentLoaded', () => {
    // Create a <style> element to hold all our new CSS rules.
    const styleSheet = document.createElement("style");

    // Define the CSS for the animated background image and subtle component animations.
    styleSheet.innerText = `
        /* --- Keyframe Animation for the Background Image --- */
        @keyframes backgroundAnimate {
            0% {
                transform: scale(1.1) rotate(-1deg);
                filter: saturate(100%) brightness(1);
            }
            50% {
                transform: scale(1.2) rotate(1deg);
                filter: saturate(120%) brightness(1.1);
            }
            100% {
                transform: scale(1.1) rotate(-1deg);
                filter: saturate(100%) brightness(1);
            }
        }

        /* --- Animated Background using Pseudo-element (Image Animation) --- */
        /* This prevents the animation from affecting the layout of your content */
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            z-index: -2; /* Place it behind everything */
            
            /* A royalty-free abstract image from Unsplash that fits the theme */
            background-image: url('https://images.unsplash.com/photo-1554141542-026c5970c0ba?q=80&w=2070&auto=format&fit=crop');
            background-size: cover;
            background-position: center;
            
            /* Apply the new, smoother animation */
            animation: backgroundAnimate 40s ease-in-out infinite alternate;
        }

        /* --- Overlay for Readability --- */
        body::after {
            content: '';
            position: fixed; /* Covers the entire viewport */
            top: 0; left: 0; width: 100%; height: 100%;
            /* Lowering opacity slightly to ensure background colors don't completely block content */
            background-color: rgba(240, 244, 248, 0.90); 
            z-index: -1; /* Places the overlay on top of the background, but behind content */
        }
        
        body {
            /* The font-family is still needed here */
            font-family: 'Inter', sans-serif; 
        }

        /* --- FIX: Ensure the main React root is above the background layers --- */
        #app-root {
            position: relative; /* Create a new stacking context */
            z-index: 1; /* Bring it above z-index: -1 and -2 */
            min-height: 100vh; /* Ensure it takes full height */
        }

        /* --- Fade-in Animation for the Main Dashboard --- */
        #app-root > .container {
             animation: fadeIn 0.8s ease-in-out forwards;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(15px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* --- Enhanced Button Animations on Hover --- */
        button, .button {
            transition: all 0.3s ease;
        }
        
        button:hover:not(:disabled), .button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }

        /* --- Subtle Card Hover Effect --- */
        .bg-white.shadow-md, .bg-white.shadow-lg, .bg-white.shadow-xl {
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .bg-white.shadow-md:hover, .bg-white.shadow-lg:hover, .bg-white.shadow-xl:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
        }
    `;

    // Add the new stylesheet to the document's <head>.
    document.head.appendChild(styleSheet);

    console.log('Advanced animations and background have been applied.');
});
