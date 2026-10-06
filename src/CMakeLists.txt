cmake_minimum_required(VERSION 3.16)
project(NoQuarter LANGUAGES C CXX)

set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Architecture and library suffix detection
if(CMAKE_SIZEOF_VOID_P EQUAL 8)
    if(WIN32)
        set(ARCH "x64")
        set(LIB_SUFFIX "_mp_")
    else()
        set(ARCH "x86_64")
        set(LIB_SUFFIX ".mp.")
    endif()
else()
    set(ARCH "x86")
    set(LIB_SUFFIX "_mp_")
endif()

if(WIN32)
    set(MOD_EXT "dll")
elseif(APPLE)
    set(MOD_EXT "dylib")
else()
    set(MOD_EXT "so")
endif()

option(BUILD_SERVER_MOD "Build qagame module" ON)
option(BUILD_CLIENT_MOD "Build cgame and ui modules" ON)
if(APPLE)
    # Omni-bot has no macOS build; macOS is a client platform for NQ EoTS
    option(WITH_OMNIBOT "Build with Omni-bot support" OFF)
else()
    option(WITH_OMNIBOT "Build with Omni-bot support" ON)
endif()
option(WITH_LUA         "Build with Lua support" ON)
option(WITH_HWBAN       "Build with Hardware Ban support" OFF)

if(MSVC)
    add_compile_options(
        /W3
        /Zi
        /wd4996 # deprecated functions
        /wd4244 # conversion possible loss of data
        /wd4305 # truncation
        /wd4018 # signed/unsigned mismatch
        /wd4267 # size_t to int conversion
        /MP     # multi-processor compilation
    )
    # [NQ 1.3.1 - Release]: don't embed the builder's folder paths in the shipped DLLs.
    # /d1trimfile strips the repo root from __FILE__ strings (src\game\... instead of C:\Users\...),
    # /PDBALTPATH:%_PDB% records only the .pdb file name instead of its full path.
    # The .pdb files are still generated for debugging; keep them next to the DLL to use them.
    file(TO_NATIVE_PATH "${CMAKE_SOURCE_DIR}" NQ_SOURCE_ROOT_NATIVE)
    add_compile_options("/d1trimfile:${NQ_SOURCE_ROOT_NATIVE}")
    set(CMAKE_SHARED_LINKER_FLAGS_RELEASE "${CMAKE_SHARED_LINKER_FLAGS_RELEASE} /DEBUG")
    # Applies to every configuration (Visual Studio "Open Folder" builds use RelWithDebInfo)
    add_link_options("/PDBALTPATH:%_PDB%")
    add_definitions(-D_CRT_SECURE_NO_WARNINGS -D_CRT_NONSTDC_NO_DEPRECATE)
else()
    add_compile_options(
        -Wall
        -Wno-unused-function
        -Wno-unused-variable
        -Wno-deprecated-declarations
        -fvisibility=hidden
        # NQ declares some shared globals in headers (old C common-symbol style).
        # GCC 10+ and Apple Clang default to -fno-common, which turns that into
        # 'multiple definition' link errors. scripts/build_linux.py passes this too.
        -fcommon
    )
endif()

# Common include directories
set(COMMON_INCLUDES
    ${CMAKE_CURRENT_SOURCE_DIR}/game
    ${CMAKE_CURRENT_SOURCE_DIR}/cgame
    ${CMAKE_CURRENT_SOURCE_DIR}/ui
    ${CMAKE_CURRENT_SOURCE_DIR}/sha-1
    ${CMAKE_CURRENT_SOURCE_DIR}/../Omnibot/Common
    ${CMAKE_CURRENT_SOURCE_DIR}/../Omnibot/ET
    ${CMAKE_CURRENT_SOURCE_DIR}/lua/lua-5.1.5/src
)

# Common shared game source files
set(BG_SRC
    game/bg_animation.c
    game/bg_animgroup.c
    game/bg_campaign.c
    game/bg_character.c
    game/bg_classes.c
    game/bg_misc.c
    game/bg_pmove.c
    game/bg_slidemove.c
    game/bg_sscript.c
    game/bg_stats.c
    game/bg_tracemap.c
    game/bg_weapons.c
    game/q_math.c
    game/q_shared.c
)

# ==============================================================================
# LUA 5.1 Library
# ==============================================================================
# Lua and LuaSQL are only used by the server module (qagame, XPSave, WolfAdmin)
if(WITH_LUA AND BUILD_SERVER_MOD)
    set(LUA_SRC
        lua/lua-5.1.5/src/lapi.c
        lua/lua-5.1.5/src/lauxlib.c
        lua/lua-5.1.5/src/lbaselib.c
        lua/lua-5.1.5/src/lcode.c
        lua/lua-5.1.5/src/ldblib.c
        lua/lua-5.1.5/src/ldebug.c
        lua/lua-5.1.5/src/ldo.c
        lua/lua-5.1.5/src/ldump.c
        lua/lua-5.1.5/src/lfunc.c
        lua/lua-5.1.5/src/lgc.c
        lua/lua-5.1.5/src/linit.c
        lua/lua-5.1.5/src/liolib.c
        lua/lua-5.1.5/src/llex.c
        lua/lua-5.1.5/src/lmathlib.c
        lua/lua-5.1.5/src/lmem.c
        lua/lua-5.1.5/src/loadlib.c
        lua/lua-5.1.5/src/lobject.c
        lua/lua-5.1.5/src/lopcodes.c
        lua/lua-5.1.5/src/loslib.c
        lua/lua-5.1.5/src/lparser.c
        lua/lua-5.1.5/src/lstate.c
        lua/lua-5.1.5/src/lstring.c
        lua/lua-5.1.5/src/lstrlib.c
        lua/lua-5.1.5/src/ltable.c
        lua/lua-5.1.5/src/ltablib.c
        lua/lua-5.1.5/src/ltm.c
        lua/lua-5.1.5/src/lundump.c
        lua/lua-5.1.5/src/lvm.c
        lua/lua-5.1.5/src/lzio.c
        lua/lua-5.1.5/src/print.c
    )
    add_library(lua51 SHARED ${LUA_SRC})
    target_include_directories(lua51 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/lua/lua-5.1.5/src)
    if(NOT MSVC)
        # The Lua C API must stay exported: -fvisibility=hidden (set for all targets above)
        # hides it, and macOS then fails to link LuaSQL/qagame against lua51.
        target_compile_options(lua51 PRIVATE -fvisibility=default)
    endif()
    if(UNIX AND NOT APPLE)
        target_link_libraries(lua51 PRIVATE m dl)
    endif()
    if(WIN32)
        target_compile_definitions(lua51 PRIVATE LUA_BUILD_AS_DLL LUA_CORE LUA_LIB)
        set_target_properties(lua51 PROPERTIES
            PREFIX ""
            OUTPUT_NAME "lua5.1"
        )
    elseif(APPLE)
        target_compile_definitions(lua51 PRIVATE LUA_USE_MACOSX)
    elseif(NOT MSVC)
        target_compile_definitions(lua51 PRIVATE LUA_USE_LINUX)
    endif()

    # ==============================================================================
    # LuaSQL SQLite3 Dynamic Library (sqlite3.dll for WolfAdmin / XPSave)
    # ==============================================================================
    set(LUASQL_SRC
        luasql/luasql.c
        luasql/ls_sqlite3.c
        sqlite3/sqlite3.c
    )
    add_library(luasql_sqlite3 SHARED ${LUASQL_SRC})
    target_include_directories(luasql_sqlite3 PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/lua/lua-5.1.5/src
        ${CMAKE_CURRENT_SOURCE_DIR}/luasql
        ${CMAKE_CURRENT_SOURCE_DIR}/sqlite3
    )
    target_link_libraries(luasql_sqlite3 PRIVATE lua51)
    if(WIN32)
        target_compile_definitions(luasql_sqlite3 PRIVATE LUA_BUILD_AS_DLL SQLITE_ENABLE_COLUMN_METADATA SQLITE_ENABLE_FTS3)
    endif()
    set_target_properties(luasql_sqlite3 PROPERTIES
        PREFIX ""
        OUTPUT_NAME "sqlite3"
    )
endif()

# ==============================================================================
# QAGAME (Server Module)
# ==============================================================================
if(BUILD_SERVER_MOD)
    set(QAGAME_SRC
        ${BG_SRC}
        game/bg_profiler_hook.c
        game/etpro_mdx.c
        game/et-antiwarp.c
        game/g_active.c
        game/g_alarm.c
        game/g_antilag.c
        game/g_buddy_list.c
        game/g_character.c
        game/g_client.c
        game/g_cmds.c
        game/g_cmds_ext.c
        game/g_combat.c
        game/g_config.c
        game/g_crash.c
        game/g_fireteams.c
        game/g_items.c
        game/g_main.c
        game/g_match.c
        game/g_match_tokens.c
        game/g_mem.c
        game/g_misc.c
        game/g_missile.c
        game/g_mover.c
        game/g_multiview.c
        game/g_osfile.c
        game/g_props.c
        game/g_referee.c
        game/g_script.c
        game/g_script_actions.c
        game/g_session.c
        game/g_sha1.c
        game/g_shrubbot.c
        game/g_spawn.c
        game/g_stats.c
        game/g_strparse.c
        game/g_svcmds.c
        game/g_syscalls.c
        game/g_systemmsg.c
        game/g_target.c
        game/g_team.c
        game/g_teammapdata.c
        game/g_time.c
        game/g_trigger.c
        game/g_utils.c
        game/g_vote.c
        game/g_weapon.c
        game/g_xpsave.c
        game/geoip.c
        sha-1/sha.c
        sha-1/sha1.c
    )

    if(WITH_LUA)
        list(APPEND QAGAME_SRC game/g_lua.c)
    endif()

    if(WITH_OMNIBOT)
        list(APPEND QAGAME_SRC
            game/g_etbot_interface.cpp
            ../Omnibot/Common/BotLoadLibrary.cpp
        )
    endif()

    if(WITH_HWBAN)
        list(APPEND QAGAME_SRC
            game/bg_hwguid.c
            game/base64.c
            game/crc32.c
            game/md5.c
            game/xorcrypt.c
        )
        if(WIN32)
            list(APPEND QAGAME_SRC game/diskId32.cpp)
        endif()
    endif()

    add_library(qagame SHARED ${QAGAME_SRC})
    target_include_directories(qagame PRIVATE ${COMMON_INCLUDES})
    target_compile_definitions(qagame PRIVATE GAMEDLL NEW_ANIMS)

    if(WITH_LUA)
        target_compile_definitions(qagame PRIVATE ET_LUA)
        if(WIN32)
            target_compile_definitions(qagame PRIVATE LUA_BUILD_AS_DLL)
        endif()
        target_link_libraries(qagame PRIVATE lua51)
    endif()

    if(WITH_OMNIBOT)
        target_compile_definitions(qagame PRIVATE OMNIBOTS)
    endif()

    if(WITH_HWBAN)
        target_compile_definitions(qagame PRIVATE HW_BAN)
    endif()

    if(UNIX AND NOT APPLE)
        target_link_libraries(qagame PRIVATE m dl)
    endif()

    if(MSVC)
        target_link_options(qagame PRIVATE "/MAP")
    endif()

    set_target_properties(qagame PROPERTIES
        PREFIX ""
        OUTPUT_NAME "qagame${LIB_SUFFIX}${ARCH}"
    )
    if(APPLE)
        # [NQ EoTS - macOS]: ET:Legacy loads extension-less "qagame_mac" dylibs
        set_target_properties(qagame PROPERTIES OUTPUT_NAME "qagame_mac" SUFFIX "")
    endif()
endif()

# ==============================================================================
# CGAME (Client Game Module)
# ==============================================================================
if(BUILD_CLIENT_MOD)
    set(CGAME_SRC
        ${BG_SRC}
        game/g_match_tokens.c
        game/g_strparse.c
        ui/ui_shared.c
        cgame/cg_atmospheric.c
        cgame/cg_character.c
        cgame/cg_commandmap.c
        cgame/cg_consolecmds.c
        cgame/cg_crash.c
        cgame/cg_debriefing.c
        cgame/cg_draw.c
        cgame/cg_drawtools.c
        cgame/cg_effects.c
        cgame/cg_ents.c
        cgame/cg_event.c
        cgame/cg_fireteamoverlay.c
        cgame/cg_fireteams.c
        cgame/cg_flamethrower.c
        cgame/cg_info.c
        cgame/cg_limbopanel.c
        cgame/cg_loadpanel.c
        cgame/cg_localents.c
        cgame/cg_main.c
        cgame/cg_marks.c
        cgame/cg_missionbriefing.c
        cgame/cg_missionmessages.c
        cgame/cg_multiview.c
        cgame/cg_newDraw.c
        cgame/cg_particles.c
        cgame/cg_players.c
        cgame/cg_playerstate.c
        cgame/cg_polybus.c
        cgame/cg_popupmessages.c
        cgame/cg_predict.c
        cgame/cg_scoreboard.c
        cgame/cg_servercmds.c
        cgame/cg_snapshot.c
        cgame/cg_sound.c
        cgame/cg_spawn.c
        cgame/cg_statsranksmedals.c
        cgame/cg_syscalls.c
        cgame/cg_trails.c
        cgame/cg_view.c
        cgame/cg_weapons.c
        cgame/cg_window.c
    )

    add_library(cgame SHARED ${CGAME_SRC})
    target_include_directories(cgame PRIVATE ${COMMON_INCLUDES})
    target_compile_definitions(cgame PRIVATE CGAMEDLL NEW_ANIMS)

    if(UNIX AND NOT APPLE)
        target_link_libraries(cgame PRIVATE m dl)
    endif()

    set_target_properties(cgame PROPERTIES
        PREFIX ""
        OUTPUT_NAME "cgame${LIB_SUFFIX}${ARCH}"
    )
    if(APPLE)
        # [NQ EoTS - macOS]: ET:Legacy loads extension-less "cgame_mac" dylibs
        set_target_properties(cgame PROPERTIES OUTPUT_NAME "cgame_mac" SUFFIX "")
    endif()

    # ==============================================================================
    # UI (User Interface Module)
    # ==============================================================================
    set(UI_SRC
        game/bg_campaign.c
        game/bg_classes.c
        game/bg_misc.c
        game/q_math.c
        game/q_shared.c
        ui/ui_atoms.c
        ui/ui_gameinfo.c
        ui/ui_loadpanel.c
        ui/ui_main.c
        ui/ui_shared.c
        ui/ui_syscalls.c
    )

    add_library(ui SHARED ${UI_SRC})
    target_include_directories(ui PRIVATE ${COMMON_INCLUDES})
    target_compile_definitions(ui PRIVATE UIDLL NEW_ANIMS)

    if(UNIX AND NOT APPLE)
        target_link_libraries(ui PRIVATE m dl)
    endif()

    set_target_properties(ui PROPERTIES
        PREFIX ""
        OUTPUT_NAME "ui${LIB_SUFFIX}${ARCH}"
    )
    if(APPLE)
        # [NQ EoTS - macOS]: ET:Legacy loads extension-less "ui_mac" dylibs
        set_target_properties(ui PROPERTIES OUTPUT_NAME "ui_mac" SUFFIX "")
    endif()
endif()
