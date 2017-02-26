// https://github.com/tiratatp/facebook_adblock
(function() {
    "use strict";
    function hide_if_sponsored(e) {
        // if e contains ._m8c or .uiStreamSponsoredLink, then hide
        ["_m8c", "uiStreamSponsoredLink"].forEach(function(className) {
            if (e.getElementsByClassName(className).length !== 0) {
                e.style.display = "none";
                console.info("AD Blocked", e);
            }
        });
    }

    function remove_sponsored_posts(c) {
        // new version has ".fbUserContent" instead of .userContentWrapper
        ["fbUserContent", "userContentWrapper"].forEach(function(className) {
            Array.prototype.forEach.call(c.getElementsByClassName(className), hide_if_sponsored);
        });
    }

    function onPageChange() {
        var stream_pagelet = document.getElementById("stream_pagelet");
        // if the user change page to homepage
        if (stream_pagelet !== null) {
            remove_sponsored_posts(stream_pagelet);
            stream_observer.observe(stream_pagelet, {childList: true, subtree: true});
        } else {
            // removing old observers
            stream_observer.disconnect();
        }
    }

    var sheet = window.document.styleSheets[0]
    sheet.insertRule("#stream_pagelet{height:10000px!important}", sheet.cssRules.length);
    sheet.insertRule(".rhcFooter,#pagelet_ego_pane,#MRoot article[data-xt]{display:none!important}", sheet.cssRules.length);
    sheet.insertRule(".home_right_column{min-height:inherit!important}", sheet.cssRules.length);

    var fb_content = document.getElementsByClassName("fb_content")[0],      
        fb_observer = new MutationObserver(onPageChange),
        stream_observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.target.dataset.hasOwnProperty("cursor")) {
                    remove_sponsored_posts(mutation.target);
                }
            });
        });

    // if we can't find ".fb_content", then it must be a mobile website.
    // in that case, we don't need javascript to block ads
    if (fb_content !== undefined) {
        // remove on first load
        onPageChange();

        // Facebook uses ajax to load new content so
        // we need this to watch for page change
        fb_observer.observe(fb_content, {childList: true});
    }
}());

