import argparse
import os
import re
import tempfile

BOOL_KEYS = {
    "decoration:blur:enabled",
    "decoration:shadow:enabled",
    "animations:enabled",
    "input:numlock_by_default",
    "input:touchpad:natural_scroll",
    "input:touchpad:disable_while_typing",
    "input:touchpad:clickfinger_behavior",
}

ANIM_PRESETS = {
    "elastic": """\
hl.curve("pc_wobble", { type = "bezier", points = { {0.15, 1.15}, {0.35, 1.0}  } })
hl.curve("pc_decel",  { type = "bezier", points = { {0.05, 0.9},  {0.1,  1.05} } })
hl.curve("pc_accel",  { type = "bezier", points = { {0.3,  0},    {0.8,  0.15} } })
hl.animation({ leaf = "windowsIn",           enabled = true, speed = 5, bezier = "pc_wobble", style = "slide"     })
hl.animation({ leaf = "windowsOut",          enabled = true, speed = 5, bezier = "pc_accel",  style = "slide"     })
hl.animation({ leaf = "windowsMove",         enabled = true, speed = 5, bezier = "pc_decel",  style = "slide"     })
hl.animation({ leaf = "fadeIn",              enabled = true, speed = 4, bezier = "pc_decel"                       })
hl.animation({ leaf = "fadeOut",             enabled = true, speed = 4, bezier = "pc_accel"                       })
hl.animation({ leaf = "layersIn",            enabled = true, speed = 4, bezier = "pc_decel",  style = "slide"     })
hl.animation({ leaf = "layersOut",           enabled = true, speed = 4, bezier = "pc_accel",  style = "slide"     })
hl.animation({ leaf = "workspaces",          enabled = true, speed = 6, bezier = "pc_decel",  style = "slide"     })
hl.animation({ leaf = "specialWorkspaceIn",  enabled = true, speed = 2, bezier = "pc_wobble", style = "slidevert" })
hl.animation({ leaf = "specialWorkspaceOut", enabled = true, speed = 2, bezier = "pc_accel",  style = "slidevert" })
""",
    "normal": """\
hl.curve("emphasizedDecel", { type = "bezier", points = { {0.05, 0.7},  {0.1,  1}    } })
hl.curve("emphasizedAccel", { type = "bezier", points = { {0.3,  0},    {0.8,  0.15} } })
hl.curve("menu_decel",      { type = "bezier", points = { {0.1,  1},    {0,    1}    } })
hl.curve("menu_accel",      { type = "bezier", points = { {0.52, 0.03}, {0.72, 0.08} } })
hl.curve("stall",           { type = "bezier", points = { {1,    -0.1}, {0.7,  0.85} } })
hl.animation({ leaf = "windowsIn",           enabled = true, speed = 3,   bezier = "emphasizedDecel", style = "popin 80%" })
hl.animation({ leaf = "windowsOut",          enabled = true, speed = 2,   bezier = "emphasizedDecel", style = "popin 90%" })
hl.animation({ leaf = "windowsMove",         enabled = true, speed = 3,   bezier = "emphasizedDecel", style = "slide"     })
hl.animation({ leaf = "fadeIn",              enabled = true, speed = 3,   bezier = "emphasizedDecel"  })
hl.animation({ leaf = "fadeOut",             enabled = true, speed = 2,   bezier = "emphasizedDecel"  })
hl.animation({ leaf = "border",              enabled = true, speed = 10,  bezier = "emphasizedDecel"  })
hl.animation({ leaf = "layersIn",            enabled = true, speed = 2.7, bezier = "emphasizedDecel", style = "popin 93%" })
hl.animation({ leaf = "layersOut",           enabled = true, speed = 2.4, bezier = "menu_accel",      style = "popin 94%" })
hl.animation({ leaf = "fadeLayersIn",        enabled = true, speed = 0.5, bezier = "menu_decel"       })
hl.animation({ leaf = "fadeLayersOut",       enabled = true, speed = 2.7, bezier = "stall"            })
hl.animation({ leaf = "workspaces",          enabled = true, speed = 7,   bezier = "menu_decel",      style = "slide"     })
hl.animation({ leaf = "specialWorkspaceIn",  enabled = true, speed = 2.8, bezier = "emphasizedDecel", style = "slidevert" })
hl.animation({ leaf = "specialWorkspaceOut", enabled = true, speed = 1.2, bezier = "emphasizedAccel", style = "slidevert" })
""",
    "niri": """\
hl.curve("niri_wobble", { type = "bezier", points = { {0.15, 1.15}, {0.35, 1.0}  } })
hl.curve("niri_decel",  { type = "bezier", points = { {0.05, 0.9},  {0.1,  1.05} } })
hl.curve("niri_accel",  { type = "bezier", points = { {0.3,  0},    {0.8,  0.15} } })
hl.animation({ leaf = "windowsIn",           enabled = true, speed = 5, bezier = "niri_wobble", style = "slide"     })
hl.animation({ leaf = "windowsOut",          enabled = true, speed = 5, bezier = "niri_accel",  style = "slide"     })
hl.animation({ leaf = "windowsMove",         enabled = true, speed = 5, bezier = "niri_decel",  style = "slide"     })
hl.animation({ leaf = "fadeIn",              enabled = true, speed = 4, bezier = "niri_decel"                       })
hl.animation({ leaf = "fadeOut",             enabled = true, speed = 4, bezier = "niri_accel"                       })
hl.animation({ leaf = "layersIn",            enabled = true, speed = 4, bezier = "niri_decel",  style = "slide"     })
hl.animation({ leaf = "layersOut",           enabled = true, speed = 4, bezier = "niri_accel",  style = "slide"     })
hl.animation({ leaf = "workspaces",          enabled = true, speed = 6, bezier = "niri_decel",  style = "slidevert" })
hl.animation({ leaf = "specialWorkspaceIn",  enabled = true, speed = 4, bezier = "niri_wobble", style = "slidevert" })
hl.animation({ leaf = "specialWorkspaceOut", enabled = true, speed = 4, bezier = "niri_accel",  style = "slidevert" })
""",
    "default": """\
hl.animation({leaf = "windowsIn",enabled = true,speed = 3,bezier = "default"})
hl.animation({leaf = "windowsOut",enabled = true,speed = 3,bezier = "default"})
hl.animation({leaf = "workspaces",enabled = true,speed = 5,bezier = "default"})
hl.animation({leaf = "windowsMove",enabled = true,speed = 4,bezier = "default"})
hl.animation({leaf = "fade",enabled = true,speed = 3,bezier = "default"})
hl.animation({leaf = "border",enabled = true,speed = 3,bezier = "default"})
""",
    "classic": """\
-- prod utilizes the stored hyde.config.anim.duration_scale to dynamically change anim speed!
local prod = function(ds)
    return ds * 0.9
end
hl.curve("myBezier", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.05}}})
hl.animation({leaf = "windows", enabled = true, speed = prod(7), bezier = "myBezier"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(7), bezier = "default", style = "popin 80%"})
hl.animation({leaf = "border", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "borderangle", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fade", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(7), bezier = "myBezier"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(7), bezier = "myBezier"})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadePopups", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadePopupsIn", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadePopupsOut", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeDpms", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "specialWorkspaceOut", enabled = true, speed = prod(6), bezier = "default"})
""",
    "simple": """\
hl.curve("overshot"    , { type = "bezier" , points = { {0.05 , 0.9} , {0.1  , 1.1  } } })
hl.curve("softSnap"    , { type = "bezier" , points = { {0.4  , 0  } , {0.2  , 1    } } })
hl.curve("fluent"      , { type = "bezier" , points = { {0.0  , 0.0} , {0.2  , 1.0  } } })
hl.curve("linear"      , { type = "bezier" , points = { {0    , 0  } , {1    , 1    } } })
hl.curve("almostLinear", { type = "bezier" , points = { {0.5  , 0.5} , {0.75 , 1    } } })
hl.curve("quick"       , { type = "bezier" , points = { {0.15 , 0  } , {0.1  , 1    } } })
hl.curve("smoothIn"    , { type = "bezier" , points = { {0.25 , 1  } , {0.5  , 1    } } })
hl.curve("smoothOut"   , { type = "bezier" , points = { {0.36 , 0  } , {0.66 , -0.56} } })

-- ease in
hl.curve("easeInSine"  , { type = "bezier", points = { {0.12 , 0}, {0.39 , 0    } } })
hl.curve("easeInQuad"  , { type = "bezier", points = { {0.11 , 0}, {0.5  , 0    } } })
hl.curve("easeInCubic" , { type = "bezier", points = { {0.32 , 0}, {0.67 , 0    } } })
hl.curve("easeInQuart" , { type = "bezier", points = { {0.5  , 0}, {0.75 , 0    } } })
hl.curve("easeInQuint" , { type = "bezier", points = { {0.64 , 0}, {0.78 , 0    } } })
hl.curve("easeInExpo"  , { type = "bezier", points = { {0.7  , 0}, {0.84 , 0    } } })
hl.curve("easeInCirc"  , { type = "bezier", points = { {0.55 , 0}, {1    , 0.45 } } })
hl.curve("easeInBack"  , { type = "bezier", points = { {0.36 , 0}, {0.66 , -0.56} } })

-- ease out
hl.curve("easeOutSine" , { type = "bezier", points = { {0.61 , 1   } , {0.88 , 1} } })
hl.curve("easeOutQuad" , { type = "bezier", points = { {0.5  , 1   } , {0.89 , 1} } })
hl.curve("easeOutCubic", { type = "bezier", points = { {0.33 , 1   } , {0.68 , 1} } })
hl.curve("easeOutQuart", { type = "bezier", points = { {0.25 , 1   } , {0.5  , 1} } })
hl.curve("easeOutQuint", { type = "bezier", points = { {0.22 , 1   } , {0.36 , 1} } })
hl.curve("easeOutExpo" , { type = "bezier", points = { {0.16 , 1   } , {0.3  , 1} } })
hl.curve("easeOutCirc" , { type = "bezier", points = { {0    , 0.55} , {0.45 , 1} } })
hl.curve("easeOutBack" , { type = "bezier", points = { {0.34 , 1.56} , {0.64 , 1} } })

-- ease in-out
hl.curve("easeInOutSine"  , { type = "bezier", points = { {0.37 , 0   } , {0.63 , 1   } } })
hl.curve("easeInOutQuad"  , { type = "bezier", points = { {0.45 , 0   } , {0.55 , 1   } } })
hl.curve("easeInOutCubic" , { type = "bezier", points = { {0.65 , 0   } , {0.35 , 1   } } })
hl.curve("easeInOutQuart" , { type = "bezier", points = { {0.76 , 0   } , {0.24 , 1   } } })
hl.curve("easeInOutQuint" , { type = "bezier", points = { {0.83 , 0   } , {0.17 , 1   } } })
hl.curve("easeInOutExpo"  , { type = "bezier", points = { {0.87 , 0   } , {0.13 , 1   } } })
hl.curve("easeInOutCirc"  , { type = "bezier", points = { {0.85 , 0   } , {0.15 , 1   } } })
hl.curve("easeInOutBack"  , { type = "bezier", points = { {0.68 , -0.6} , {0.32 , 1.6 } } })


hl.animation({ leaf = "windows"             , enabled = true , speed = 7 , bezier = "easeInOutQuint" })
hl.animation({ leaf = "windowsIn"           , enabled = true , speed = 7 , bezier = "easeInOutQuint" , style = "popin 75%" })
hl.animation({ leaf = "windowsOut"          , enabled = true , speed = 5 , bezier = "easeInOutQuint" })
hl.animation({ leaf = "windowsMove"         , enabled = true , speed = 4 , bezier = "softSnap" })

hl.animation({ leaf = "layers"              , enabled = true , speed = 5 , bezier = "easeInOutQuint" , style = "popin 75%" })
hl.animation({ leaf = "layersIn"            , enabled = true , speed = 5 , bezier = "easeInOutQuint" , style = "popin 75%" })
hl.animation({ leaf = "layersOut"           , enabled = true , speed = 7 , bezier = "easeInOutQuint" , style = "popin 75%" })

hl.animation({ leaf = "fade"                , enabled = true , speed = 5 , bezier = "easeOutQuint" })
hl.animation({ leaf = "fadeIn"              , enabled = true , speed = 5 , bezier = "easeOutQuint" })
hl.animation({ leaf = "fadeOut"             , enabled = true , speed = 7 , bezier = "easeOutQuint" })
hl.animation({ leaf = "fadeSwitch"          , enabled = true , speed = 5 , bezier = "easeInOutQuint" })
hl.animation({ leaf = "fadeShadow"          , enabled = true , speed = 5 , bezier = "easeInOutQuint" })
hl.animation({ leaf = "fadeDim"             , enabled = true , speed = 7 , bezier = "easeInOutQuint" })
hl.animation({ leaf = "fadeLayers"          , enabled = true , speed = 5 , bezier = "easeOutQuint" })
hl.animation({ leaf = "fadeLayersIn"        , enabled = true , speed = 5 , bezier = "easeOutQuint" })
hl.animation({ leaf = "fadeLayersOut"       , enabled = true , speed = 7 , bezier = "easeOutQuint" })

hl.animation({ leaf = "border"              , enabled = true , speed = 7  , bezier = "easeOutQuint" })
hl.animation({ leaf = "borderangle"         , enabled = true , speed = 15 , bezier = "easeOutBack" })

hl.animation({ leaf = "workspaces"          , enabled = true , speed = 7 , bezier = "easeOutQuint" , style = "slidefade 10%" })
hl.animation({ leaf = "workspacesIn"        , enabled = true , speed = 7 , bezier = "easeOutQuint" , style = "slidefade 10%" })
hl.animation({ leaf = "workspacesOut"       , enabled = true , speed = 5 , bezier = "easeOutQuint" , style = "slidefade 10%" })
hl.animation({ leaf = "specialWorkspace"    , enabled = true , speed = 7 , bezier = "easeOutQuint" , style = "slidefadevert -10%" })
hl.animation({ leaf = "specialWorkspaceIn"  , enabled = true , speed = 7 , bezier = "easeOutQuint" , style = "slidefadevert -10%" })
hl.animation({ leaf = "specialWorkspaceOut" , enabled = true , speed = 7 , bezier = "easeOutQuint" , style = "slidefadevert -10%" })
""",
    "diablo-1": """\
local prod = function(ds)
    return ds * 0.9
end

hl.curve("default", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.05}}})
hl.curve("wind", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.05}}})
hl.curve("overshot", {type = "bezier", points = {{0.13, 0.99}, {0.29, 1.08}}})
hl.curve("liner", {type = "bezier", points = {{1, 1}, {1, 1}}})
hl.curve("bounce", {type = "bezier", points = {{0.4, 0.9}, {0.6, 1.0}}})
hl.curve("snappyReturn", {type = "bezier", points = {{0.4, 0.9}, {0.6, 1.0}}})
hl.curve("slideInFromRight", {type = "bezier", points = {{0.5, 0.0}, {0.5, 1.0}}})
hl.animation({leaf = "layersIn", enabled = true, speed = prod(4), bezier = "bounce", style = "slidevert right"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "windows", enabled = true, speed = prod(5), bezier = "snappyReturn", style = "slidevert"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(5), bezier = "snappyReturn", style = "slidevert right"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(5), bezier = "snappyReturn", style = "slide"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(6), bezier = "bounce", style = "slide"})
hl.animation({leaf = "layersOut", enabled = true, speed = prod(5), bezier = "bounce", style = "slidevert right"})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "border", enabled = true, speed = prod(1), bezier = "liner"})
hl.animation({leaf = "layers", enabled = true, speed = prod(4), bezier = "bounce", style = "slidevert right"})
hl.animation({leaf = "borderangle", enabled = true, speed = prod(30), bezier = "liner", style = "loop"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "specialWorkspaceOut", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
""",
    "diablo-2": """\
local prod = function(ds)
    return ds * 0.9
end

hl.curve("default", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.05}}})
hl.curve("wind", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.05}}})
hl.curve("overshot", {type = "bezier", points = {{0.13, 0.99}, {0.29, 1.08}}})
hl.curve("liner", {type = "bezier", points = {{1, 1}, {1, 1}}})
hl.animation({leaf = "layersIn", enabled = true, speed = prod(5), bezier = "default", style = "popin"})
hl.animation({leaf = "layersOut", enabled = true, speed = prod(5), bezier = "default", style = "popin"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "windows", enabled = true, speed = prod(7), bezier = "wind", style = "popin"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(7), bezier = "overshot", style = "popin"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(5), bezier = "overshot", style = "popin"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(6), bezier = "overshot", style = "slide"})
hl.animation({leaf = "layers", enabled = true, speed = prod(5), bezier = "default", style = "popin"})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "border", enabled = true, speed = prod(1), bezier = "liner"})
hl.animation({leaf = "borderangle", enabled = true, speed = prod(30), bezier = "liner", style = "loop"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "specialWorkspaceOut", enabled = true, speed = prod(7), bezier = "overshot", style = "slidevert"})
""", 
    "end4": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("linear", {type = "bezier", points = {{0, 0}, {1, 1}}})
hl.curve("md3_standard", {type = "bezier", points = {{0.2, 0}, {0, 1}}})
hl.curve("md3_decel", {type = "bezier", points = {{0.05, 0.7}, {0.1, 1}}})
hl.curve("md3_accel", {type = "bezier", points = {{0.3, 0}, {0.8, 0.15}}})
hl.curve("overshot", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.1}}})
hl.curve("crazyshot", {type = "bezier", points = {{0.1, 1.5}, {0.76, 0.92}}})
hl.curve("hyprnostretch", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.0}}})
hl.curve("menu_decel", {type = "bezier", points = {{0.1, 1}, {0, 1}}})
hl.curve("menu_accel", {type = "bezier", points = {{0.38, 0.04}, {1, 0.07}}})
hl.curve("easeInOutCirc", {type = "bezier", points = {{0.85, 0}, {0.15, 1}}})
hl.curve("easeOutCirc", {type = "bezier", points = {{0, 0.55}, {0.45, 1}}})
hl.curve("easeOutExpo", {type = "bezier", points = {{0.16, 1}, {0.3, 1}}})
hl.curve("softAcDecel", {type = "bezier", points = {{0.26, 0.26}, {0.15, 1}}})
hl.curve("md2", {type = "bezier", points = {{0.4, 0}, {0.2, 1}}})

hl.animation({leaf = "windows", enabled = true, speed = prod(3), bezier = "md3_decel", style = "popin 60%"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(3), bezier = "md3_decel", style = "popin 60%"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(3), bezier = "md3_accel", style = "popin 60%"})
hl.animation({leaf = "border", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fade", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "layersIn", enabled = true, speed = prod(3), bezier = "menu_decel", style = "slide"})
hl.animation({leaf = "layersOut", enabled = true, speed = prod(1.6), bezier = "menu_accel"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(2), bezier = "menu_decel"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(4.5), bezier = "menu_accel"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(7), bezier = "menu_decel", style = "slide"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(3), bezier = "md3_decel", style = "slidevert"})
""", 
    "fastest": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("linear", {type = "bezier", points = {{0, 0}, {1, 1}}})
hl.curve("md3_standard", {type = "bezier", points = {{0.2, 0}, {0, 1}}})
hl.curve("md3_decel", {type = "bezier", points = {{0.05, 0.7}, {0.1, 1}}})
hl.curve("md3_accel", {type = "bezier", points = {{0.3, 0}, {0.8, 0.15}}})
hl.curve("overshot", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.1}}})
hl.curve("crazyshot", {type = "bezier", points = {{0.1, 1.5}, {0.76, 0.92}}})
hl.curve("hyprnostretch", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.0}}})
hl.curve("fluent_decel", {type = "bezier", points = {{0.1, 1}, {0, 1}}})
hl.curve("easeInOutCirc", {type = "bezier", points = {{0.85, 0}, {0.15, 1}}})
hl.curve("easeOutCirc", {type = "bezier", points = {{0, 0.55}, {0.45, 1}}})
hl.curve("easeOutExpo", {type = "bezier", points = {{0.16, 1}, {0.3, 1}}})

hl.animation({leaf = "windowsIn", enabled = true, speed = prod(3), bezier = "md3_decel", style = "popin 60%"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(3), bezier = "md3_decel", style = "popin 60%"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(3), bezier = "md3_decel", style = "popin 60%"})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "fadePopups", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "fadeDpms", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(3.5), bezier = "easeOutExpo", style = "slide"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(3.5), bezier = "easeOutExpo", style = "slide"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(3), bezier = "md3_decel", style = "slidevert"})
hl.animation({leaf = "specialWorkspaceOut", enabled = true, speed = prod(3), bezier = "md3_decel", style = "slidevert"})
hl.animation({leaf = "windows", enabled = true, speed = prod(3), bezier = "md3_decel", style = "popin 60%"})
hl.animation({leaf = "border", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "fade", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(3.5), bezier = "easeOutExpo", style = "slide"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(3), bezier = "md3_decel", style = "slidevert"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "fadePopupsIn", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
hl.animation({leaf = "fadePopupsOut", enabled = true, speed = prod(2.5), bezier = "md3_decel"})
""", 
    "gnome": """\
local prod = function(ds)
    return ds * 0.9
end

hl.curve("gnomeOpen", {type = "spring", mass = 1, stiffness = 100, dampening = 14})
hl.curve("gnomeClose", {type = "spring", mass = 1, stiffness = 90, dampening = 16})
hl.curve("gnomeFade", {type = "bezier", points = {{0.25, 0.1}, {0.25, 1.0}}})

hl.animation({leaf = "windowsIn", enabled = true, speed = prod(7), spring = "gnomeOpen", style = "gnomed"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(6), spring = "gnomeClose", style = "gnomed"})

hl.animation({leaf = "windowsMove", enabled = true, speed = prod(5), bezier = "gnomeFade", style = "slide"})
hl.animation({leaf = "border", enabled = true, speed = prod(1), bezier = "default"})
hl.animation({leaf = "borderangle", enabled = true, speed = prod(30), bezier = "default", style = "once"})
hl.animation({leaf = "fade", enabled = true, speed = prod(9), bezier = "default"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(6), bezier = "gnomeFade", style = "slidefade 20%"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(6), bezier = "gnomeFade", style = "slidefade 20%"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(6), bezier = "gnomeFade", style = "slidefade 20%"})
hl.animation(
    {leaf = "specialWorkspace", enabled = true, speed = prod(6), bezier = "gnomeFade", style = "slidefade 20%"}
)
hl.animation(
    {leaf = "specialWorkspaceIn", enabled = true, speed = prod(6), bezier = "gnomeFade", style = "slidefade 20%"}
)
hl.animation(
    {leaf = "specialWorkspaceOut", enabled = true, speed = prod(6), bezier = "gnomeFade", style = "slidefade 20%"}
)
hl.animation({leaf = "zoomFactor", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "monitorAdded", enabled = true, speed = prod(7), bezier = "default"})
""",
    "ja": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("wind", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.05}}})
hl.curve("winIn", {type = "bezier", points = {{0.1, 1.1}, {0.1, 1.1}}})
hl.curve("winOut", {type = "bezier", points = {{0.3, -0.3}, {0, 1}}})
hl.curve("liner", {type = "bezier", points = {{1, 1}, {1, 1}}})
hl.curve("overshot", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.05}}})
hl.curve("smoothOut", {type = "bezier", points = {{0.5, 0}, {0.99, 0.99}}})
hl.curve("smoothIn", {type = "bezier", points = {{0.5, -0.5}, {0.68, 1.5}}})

hl.animation({leaf = "windows", enabled = true, speed = prod(6), bezier = "wind", style = "slide"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(5), bezier = "winIn", style = "slide"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(3), bezier = "smoothOut", style = "slide"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(5), bezier = "wind", style = "slide"})
hl.animation({leaf = "border", enabled = true, speed = prod(1), bezier = "liner"})
hl.animation({leaf = "fade", enabled = true, speed = prod(3), bezier = "smoothOut"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(5), bezier = "overshot"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(5), bezier = "winIn", style = "slide"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(5), bezier = "winOut", style = "slide"})
""",
    "limefrenzy": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("default", {type = "bezier", points = {{0.12, 0.92}, {0.08, 1.0}}})
hl.curve("wind", {type = "bezier", points = {{0.12, 0.92}, {0.08, 1.0}}})
hl.curve("overshot", {type = "bezier", points = {{0.18, 0.95}, {0.22, 1.03}}})
hl.curve("liner", {type = "bezier", points = {{1, 1}, {1, 1}}})

hl.animation({leaf = "layersIn", enabled = true, speed = prod(4), bezier = "default", style = "popin"})
hl.animation({leaf = "layersOut", enabled = true, speed = prod(4), bezier = "default", style = "popin"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(5), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(5), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(5), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "windows", enabled = true, speed = prod(5), bezier = "wind", style = "popin 60%"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(6), bezier = "overshot", style = "popin 60%"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(4), bezier = "overshot", style = "popin 60%"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(4), bezier = "overshot", style = "slide"})
hl.animation({leaf = "layers", enabled = true, speed = prod(4), bezier = "default", style = "popin"})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(5), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "border", enabled = true, speed = prod(1), bezier = "liner"})
hl.animation({leaf = "borderangle", enabled = true, speed = prod(24), bezier = "liner", style = "loop"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(5), bezier = "overshot", style = "slidevert"})
hl.animation({leaf = "specialWorkspaceOut", enabled = true, speed = prod(5), bezier = "overshot", style = "slidevert"})
""",
    "macos": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("macOpen", {type = "spring", mass = 1, stiffness = 110, dampening = 16})
hl.curve("macBounce", {type = "spring", mass = 1, stiffness = 80, dampening = 10})
hl.curve("macSmooth", {type = "bezier", points = {{0.25, 0.1}, {0.25, 1.0}}})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fadePopups", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fadePopupsIn", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fadePopupsOut", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fadeDpms", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "windows", enabled = true, speed = prod(8), spring = "macOpen", style = "popin 90%"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(8), spring = "macOpen", style = "popin 90%"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(7), spring = "macBounce", style = "popin 90%"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(5), bezier = "macSmooth", style = "slide"})
hl.animation({leaf = "border", enabled = true, speed = prod(1), bezier = "default"})
hl.animation({leaf = "borderangle", enabled = true, speed = prod(30), bezier = "default", style = "once"})
hl.animation({leaf = "fade", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(6), bezier = "macSmooth", style = "slidefade 20%"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(6), bezier = "macSmooth", style = "slidefade 20%"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(6), bezier = "macSmooth", style = "slidefade 20%"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(6), bezier = "macSmooth", style = "slidefade 20%"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(6), bezier = "macSmooth", style = "slidefade 20%"})
hl.animation({leaf = "specialWorkspaceOut", enabled = true, speed = prod(6), bezier = "macSmooth", style = "slidefade 20%"})
hl.animation({leaf = "zoomFactor", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "monitorAdded", enabled = true, speed = prod(7), bezier = "default"})
""",
    "me-1": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("wind", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.05}}})
hl.curve("winIn", {type = "bezier", points = {{0.1, 1.1}, {0.1, 1.1}}})
hl.curve("winOut", {type = "bezier", points = {{0.3, -0.3}, {0, 1}}})
hl.curve("liner", {type = "bezier", points = {{1, 1}, {1, 1}}})
hl.curve("md3_standard", {type = "bezier", points = {{0.2, 0}, {0, 1}}})
hl.curve("md3_decel", {type = "bezier", points = {{0.05, 0.7}, {0.1, 1}}})
hl.curve("md3_accel", {type = "bezier", points = {{0.3, 0}, {0.8, 0.15}}})
hl.curve("overshot", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.1}}})
hl.curve("crazyshot", {type = "bezier", points = {{0.1, 1.5}, {0.76, 0.92}}})
hl.curve("hyprnostretch", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.0}}})
hl.curve("menu_decel", {type = "bezier", points = {{0.1, 1}, {0, 1}}})
hl.curve("menu_accel", {type = "bezier", points = {{0.38, 0.04}, {1, 0.07}}})
hl.curve("easeInOutCirc", {type = "bezier", points = {{0.85, 0}, {0.15, 1}}})
hl.curve("easeOutCirc", {type = "bezier", points = {{0, 0.55}, {0.45, 1}}})
hl.curve("easeOutExpo", {type = "bezier", points = {{0.16, 1}, {0.3, 1}}})
hl.curve("softAcDecel", {type = "bezier", points = {{0.26, 0.26}, {0.15, 1}}})
hl.curve("md2", {type = "bezier", points = {{0.4, 0}, {0.2, 1}}})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadePopups", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeDpms", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(5), bezier = "wind"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(5), bezier = "wind"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(3), bezier = "md3_decel", style = "slidevert"})
hl.animation({leaf = "specialWorkspaceOut", enabled = true, speed = prod(3), bezier = "md3_decel", style = "slidevert"})
hl.animation({leaf = "border", enabled = true, speed = prod(1), bezier = "liner"})
hl.animation({leaf = "borderangle", enabled = true, speed = prod(30), bezier = "liner", style = "loop"})
hl.animation({leaf = "windows", enabled = true, speed = prod(6), bezier = "wind", style = "slide"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(6), bezier = "winIn", style = "slide"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(5), bezier = "winOut", style = "slide"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(5), bezier = "wind", style = "slide"})
hl.animation({leaf = "fade", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "layersIn", enabled = true, speed = prod(3), bezier = "menu_decel", style = "slide"})
hl.animation({leaf = "layersOut", enabled = true, speed = prod(1.6), bezier = "menu_accel"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(2), bezier = "menu_decel"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(4.5), bezier = "menu_accel"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(5), bezier = "wind"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(3), bezier = "md3_decel", style = "slidevert"})
hl.animation({leaf = "fadePopupsIn", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadePopupsOut", enabled = true, speed = prod(3), bezier = "md3_decel"})
""",
    "me-2": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("wind", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.05}}})
hl.curve("winIn", {type = "bezier", points = {{0.1, 1.1}, {0.1, 1.1}}})
hl.curve("winOut", {type = "bezier", points = {{0.3, -0.3}, {0, 1}}})
hl.curve("liner", {type = "bezier", points = {{1, 1}, {1, 1}}})
hl.curve("md3_standard", {type = "bezier", points = {{0.2, 0}, {0, 1}}})
hl.curve("md3_decel", {type = "bezier", points = {{0.05, 0.7}, {0.1, 1}}})
hl.curve("md3_accel", {type = "bezier", points = {{0.3, 0}, {0.8, 0.15}}})
hl.curve("overshot", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.1}}})
hl.curve("crazyshot", {type = "bezier", points = {{0.1, 1.5}, {0.76, 0.92}}})
hl.curve("hyprnostretch", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.0}}})
hl.curve("menu_decel", {type = "bezier", points = {{0.1, 1}, {0, 1}}})
hl.curve("menu_accel", {type = "bezier", points = {{0.38, 0.04}, {1, 0.07}}})
hl.curve("easeInOutCirc", {type = "bezier", points = {{0.85, 0}, {0.15, 1}}})
hl.curve("easeOutCirc", {type = "bezier", points = {{0, 0.55}, {0.45, 1}}})
hl.curve("easeOutExpo", {type = "bezier", points = {{0.16, 1}, {0.3, 1}}})
hl.curve("softAcDecel", {type = "bezier", points = {{0.26, 0.26}, {0.15, 1}}})
hl.curve("md2", {type = "bezier", points = {{0.4, 0}, {0.2, 1}}})
hl.curve("OutBack", {type = "bezier", points = {{0.34, 1.56}, {0.64, 1}}})

hl.animation({leaf = "fadeIn", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadePopups", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadeDpms", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(5), bezier = "wind"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(5), bezier = "wind"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(3), bezier = "md3_decel", style = "slidevert"})
hl.animation({leaf = "specialWorkspaceOut", enabled = true, speed = prod(3), bezier = "md3_decel", style = "slidevert"})
hl.animation({leaf = "border", enabled = true, speed = prod(1), bezier = "liner"})
hl.animation({leaf = "borderangle", enabled = true, speed = prod(30), bezier = "liner", style = "loop"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(6), bezier = "winIn", style = "slide"})
hl.animation({leaf = "windows", enabled = true, speed = prod(5), bezier = "easeInOutCirc"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(5), bezier = "OutBack"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(5), bezier = "wind", style = "slide"})
hl.animation({leaf = "fade", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "layersIn", enabled = true, speed = prod(3), bezier = "menu_decel", style = "slide"})
hl.animation({leaf = "layersOut", enabled = true, speed = prod(1.6), bezier = "menu_accel"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(2), bezier = "menu_decel"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(4.5), bezier = "menu_accel"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(5), bezier = "wind"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(3), bezier = "md3_decel", style = "slidevert"})
hl.animation({leaf = "fadePopupsIn", enabled = true, speed = prod(3), bezier = "md3_decel"})
hl.animation({leaf = "fadePopupsOut", enabled = true, speed = prod(3), bezier = "md3_decel"})
""", 
    "minimal": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("quart", {type = "bezier", points = {{0.25, 1}, {0.5, 1}}})

hl.animation({leaf = "windowsIn", enabled = true, speed = prod(6), bezier = "quart", style = "slide"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(6), bezier = "quart", style = "slide"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(6), bezier = "quart", style = "slide"})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fadePopups", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fadeDpms", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "windows", enabled = true, speed = prod(6), bezier = "quart", style = "slide"})
hl.animation({leaf = "border", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "borderangle", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fade", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fadePopupsIn", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "fadePopupsOut", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(6), bezier = "quart"})
hl.animation({leaf = "specialWorkspaceOut", enabled = true, speed = prod(6), bezier = "quart"})
""",
    "moving": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("overshot", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.05}}})
hl.curve("smoothOut", {type = "bezier", points = {{0.5, 0}, {0.99, 0.99}}})
hl.curve("smoothIn", {type = "bezier", points = {{0.5, -0.5}, {0.68, 1.5}}})

hl.animation({leaf = "fadeIn", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "fadePopups", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "fadeDpms", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "windows", enabled = true, speed = prod(5), bezier = "overshot", style = "slide"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(3), bezier = "smoothOut"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(3), bezier = "smoothOut"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(4), bezier = "smoothIn", style = "slide"})
hl.animation({leaf = "border", enabled = true, speed = prod(5), bezier = "default"})
hl.animation({leaf = "fade", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "fadePopupsIn", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "fadePopupsOut", enabled = true, speed = prod(5), bezier = "smoothIn"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "specialWorkspaceOut", enabled = true, speed = prod(6), bezier = "default"})
""",
    "optimized": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("wind", {type = "bezier", points = {{0.05, 0.85}, {0.03, 0.97}}})
hl.curve("winIn", {type = "bezier", points = {{0.07, 0.88}, {0.04, 0.99}}})
hl.curve("winOut", {type = "bezier", points = {{0.20, -0.15}, {0, 1}}})
hl.curve("liner", {type = "bezier", points = {{1, 1}, {1, 1}}})
hl.curve("md3_standard", {type = "bezier", points = {{0.12, 0}, {0, 1}}})
hl.curve("md3_decel", {type = "bezier", points = {{0.05, 0.80}, {0.10, 0.97}}})
hl.curve("md3_accel", {type = "bezier", points = {{0.20, 0}, {0.80, 0.08}}})
hl.curve("overshot", {type = "bezier", points = {{0.05, 0.85}, {0.07, 1.04}}})
hl.curve("crazyshot", {type = "bezier", points = {{0.1, 1.22}, {0.68, 0.98}}})
hl.curve("hyprnostretch", {type = "bezier", points = {{0.05, 0.82}, {0.03, 0.94}}})
hl.curve("menu_decel", {type = "bezier", points = {{0.05, 0.82}, {0, 1}}})
hl.curve("menu_accel", {type = "bezier", points = {{0.20, 0}, {0.82, 0.10}}})
hl.curve("easeInOutCirc", {type = "bezier", points = {{0.75, 0}, {0.15, 1}}})
hl.curve("easeOutCirc", {type = "bezier", points = {{0, 0.48}, {0.38, 1}}})
hl.curve("easeOutExpo", {type = "bezier", points = {{0.10, 0.94}, {0.23, 0.98}}})
hl.curve("softAcDecel", {type = "bezier", points = {{0.20, 0.20}, {0.15, 1}}})
hl.curve("md2", {type = "bezier", points = {{0.30, 0}, {0.15, 1}}})
hl.curve("OutBack", {type = "bezier", points = {{0.28, 1.40}, {0.58, 1}}})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(1.8), bezier = "md3_decel"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(1.8), bezier = "md3_decel"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(1.8), bezier = "md3_decel"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(1.8), bezier = "md3_decel"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(1.8), bezier = "md3_decel"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(1.8), bezier = "md3_decel"})
hl.animation({leaf = "fadePopups", enabled = true, speed = prod(1.8), bezier = "md3_decel"})
hl.animation({leaf = "fadeDpms", enabled = true, speed = prod(1.8), bezier = "md3_decel"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(4.0), bezier = "menu_decel", style = "slide"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(4.0), bezier = "menu_decel", style = "slide"})
hl.animation(
    {leaf = "specialWorkspaceIn", enabled = true, speed = prod(2.3), bezier = "md3_decel", style = "slidefadevert 15%"}
)
hl.animation(
    {leaf = "specialWorkspaceOut", enabled = true, speed = prod(2.3), bezier = "md3_decel", style = "slidefadevert 15%"}
)
hl.animation({leaf = "border", enabled = true, speed = prod(1.6), bezier = "liner"})
hl.animation({leaf = "borderangle", enabled = true, speed = prod(82), bezier = "liner", style = "loop"})
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(3.2), bezier = "winIn", style = "slide"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(2.8), bezier = "easeOutCirc"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(3.0), bezier = "wind", style = "slide"})
hl.animation({leaf = "fade", enabled = true, speed = prod(1.8), bezier = "md3_decel"})
hl.animation({leaf = "layersIn", enabled = true, speed = prod(1.8), bezier = "menu_decel", style = "slide"})
hl.animation({leaf = "layersOut", enabled = true, speed = prod(1.5), bezier = "menu_accel"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(1.6), bezier = "menu_decel"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(1.8), bezier = "menu_accel"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(4.0), bezier = "menu_decel", style = "slide"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(4.0), bezier = "menu_decel", style = "slide"})
hl.animation(
    {leaf = "specialWorkspace", enabled = true, speed = prod(2.3), bezier = "md3_decel", style = "slidefadevert 15%"}
)
hl.animation({leaf = "fadePopupsIn", enabled = true, speed = prod(1.8), bezier = "md3_decel"})
hl.animation({leaf = "fadePopupsOut", enabled = true, speed = prod(1.8), bezier = "md3_decel"})
""",
    "standard": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("myBezier", {type = "bezier", points = {{0.05, 0.9}, {0.1, 1.05}}})

hl.animation({leaf = "windowsIn", enabled = true, speed = prod(7), bezier = "myBezier"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(7), bezier = "myBezier"})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadePopups", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeDpms", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "windows", enabled = true, speed = prod(7), bezier = "myBezier"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(7), bezier = "default", style = "popin 80%"})
hl.animation({leaf = "border", enabled = true, speed = prod(10), bezier = "default"})
hl.animation({leaf = "borderangle", enabled = true, speed = prod(8), bezier = "default"})
hl.animation({leaf = "fade", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "fadeLayersIn", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadePopupsIn", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "fadePopupsOut", enabled = true, speed = prod(7), bezier = "default"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(6), bezier = "default"})
hl.animation({leaf = "specialWorkspaceOut", enabled = true, speed = prod(6), bezier = "default"})
""", 
    "vertical": """\
local prod = function(ds)
    return ds * 0.9
end


hl.curve("fluent_decel", {type = "bezier", points = {{0, 0.2}, {0.4, 1}}})
hl.curve("easeOutCirc", {type = "bezier", points = {{0, 0.55}, {0.45, 1}}})
hl.curve("easeOutCubic", {type = "bezier", points = {{0.33, 1}, {0.68, 1}}})
hl.curve("easeinoutsine", {type = "bezier", points = {{0.37, 0}, {0.63, 1}}})

hl.animation({leaf = "layersIn", enabled = true, speed = prod(1.5), bezier = "easeinoutsine", style = "popin"})
hl.animation({leaf = "layersOut", enabled = true, speed = prod(1.5), bezier = "easeinoutsine", style = "popin"})
hl.animation({leaf = "fadeIn", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
hl.animation({leaf = "fadeOut", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
hl.animation({leaf = "fadeSwitch", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
hl.animation({leaf = "fadeShadow", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
hl.animation({leaf = "fadeDim", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
hl.animation({leaf = "fadeLayers", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
hl.animation({leaf = "fadePopups", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
hl.animation({leaf = "fadeDpms", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
hl.animation({leaf = "workspacesIn", enabled = true, speed = prod(3), bezier = "fluent_decel", style = "slidefadevert 30%"})
hl.animation({leaf = "workspacesOut", enabled = true, speed = prod(3), bezier = "fluent_decel", style = "slidefadevert 30%"})
hl.animation({leaf = "specialWorkspaceIn", enabled = true, speed = prod(2), bezier = "fluent_decel", style = "slidefade 10%"})
hl.animation(
    {leaf = "specialWorkspaceOut", enabled = true, speed = prod(2), bezier = "fluent_decel", style = "slidefade 10%"}
)
hl.animation({leaf = "windowsIn", enabled = true, speed = prod(1.5), bezier = "easeinoutsine", style = "popin 60%"})
hl.animation({leaf = "windowsOut", enabled = true, speed = prod(1.5), bezier = "easeOutCubic", style = "popin 60%"})
hl.animation({leaf = "windowsMove", enabled = true, speed = prod(1.5), bezier = "easeinoutsine", style = "slide"})
hl.animation({leaf = "fade", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
hl.animation({leaf = "fadeLayersIn", enabled = false})
hl.animation({leaf = "border", enabled = false})
hl.animation({leaf = "layers", enabled = true, speed = prod(1.5), bezier = "easeinoutsine", style = "popin"})
hl.animation({leaf = "workspaces", enabled = true, speed = prod(3), bezier = "fluent_decel", style = "slidefadevert 30%"})
hl.animation({leaf = "specialWorkspace", enabled = true, speed = prod(2), bezier = "fluent_decel", style = "slidefade 10%"})
hl.animation({leaf = "fadeLayersOut", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
hl.animation({leaf = "fadePopupsIn", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
hl.animation({leaf = "fadePopupsOut", enabled = true, speed = prod(2.5), bezier = "fluent_decel"})
"""
}


def to_lua_value(key, value):
    if key in BOOL_KEYS:
        return "false" if value == "0" else "true"
    try:
        return str(int(value))
    except ValueError:
        pass
    try:
        return str(float(value))
    except ValueError:
        pass
    return f'"{value}"'


def to_lua_line(key, value):
    parts = key.replace(":", ".").split(".")
    val = to_lua_value(key, value)
    inner = f"{{ {parts[-1]} = {val} }}"
    for part in reversed(parts[:-1]):
        inner = f"{{ {part} = {inner} }}"
    return f"hl.config({inner})\n"


def make_marker(key):
    parts = key.replace(":", ".").split(".")

    fragment = " = { ".join(parts[:-1])
    if fragment:
        fragment += " = { " + parts[-1] + " ="
    else:
        fragment = parts[-1] + " ="
    return fragment


def write_atomic(path, content):
    dir_name = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_name, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=dir_name, delete=False) as f:
            f.write(content)
            tmp_path = f.name
        if os.path.exists(path):
            os.chmod(tmp_path, os.stat(path).st_mode)
        os.replace(tmp_path, path)
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise e


def edit_lua(file_path, set_pairs, reset_keys):
    try:
        with open(file_path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    set_dict   = dict(set_pairs)
    reset_set  = set(reset_keys)
    all_keys   = list(set_dict) + list(reset_set)
    markers    = {k: make_marker(k) for k in all_keys}

    new_lines  = []
    found_keys = set()

    for line in lines:
        matched = None
        for k in all_keys:
            if markers[k] in line:
                matched = k
                break
        if matched is None:
            new_lines.append(line)
        elif matched in reset_set:
            print(f"Removed: {matched}")
        else:
            new_lines.append(to_lua_line(matched, set_dict[matched]))
            found_keys.add(matched)
            print(f"Updated: {to_lua_line(matched, set_dict[matched]).strip()}")

    for k, v in set_dict.items():
        if k not in found_keys:
            new_lines.append(to_lua_line(k, v))
            print(f"Added:   {to_lua_line(k, v).strip()}")

    write_atomic(file_path, "".join(new_lines))


def save_preset(anim_file, preset_name):
    content = ANIM_PRESETS.get(preset_name)
    if not content:
        print(f"Unknown preset '{preset_name}'")
        return
    write_atomic(anim_file, content)
    print(f"Wrote preset '{preset_name}' -> {anim_file}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--file", default="~/.config/hypr/hyprland/nandoroid/shellConfig.lua")
    p.add_argument("--set", nargs=2, action="append", metavar=("KEY", "VALUE"))
    p.add_argument("--reset", action="append", metavar="KEY")
    p.add_argument("--anim-preset", metavar="PRESET")
    p.add_argument("--anim-file", default="~/.config/hypr/nandoroid/animations.lua")
    args = p.parse_args()

    if args.anim_preset:
        save_preset(os.path.expanduser(args.anim_file), args.anim_preset)

    raw_sets   = args.set or []
    reset_keys = args.reset or []
    set_pairs  = []
    for k, v in raw_sets:
        if v == "[[EMPTY]]":
            reset_keys.append(k)
        else:
            set_pairs.append((k, v))

    if set_pairs or reset_keys:
        edit_lua(os.path.expanduser(args.file), set_pairs, reset_keys)
    elif not args.anim_preset:
        print("Error: specify --set, --reset, or --anim-preset")