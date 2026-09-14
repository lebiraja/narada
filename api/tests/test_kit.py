"""Named kit pieces, because raw GM numbers were getting written wrong."""

import pytest

from app.core.kit import BY_NAME, KIT_PRESETS, Kit, describe_kit, piece_names, resolve


class TestResolution:
    @pytest.mark.parametrize(
        ("written", "expected"),
        [
            ("kick", "kick"),
            ("Kick", "kick"),
            ("bass drum", "kick"),
            ("bass_drum", "kick"),
            ("BD", "kick"),
            ("snare", "snare"),
            ("rimshot", "snare_rim"),
            ("ghost", "ghost_snare"),
            ("hihat", "hat_closed"),
            ("hi-hat", "hat_closed"),
            ("open_hat", "hat_open"),
            ("ride cymbal", "ride"),
            ("bell", "ride_bell"),
            ("floor tom", "tom_floor"),
        ],
    )
    def test_accepts_how_a_drummer_would_write_it(self, written, expected):
        assert resolve(written).name == expected

    def test_returns_nothing_for_an_unknown_surface(self):
        assert resolve("gong") is None
        assert resolve("") is None
        assert resolve(None) is None

    def test_a_ghost_note_is_quiet_by_default(self):
        assert resolve("ghost_snare").velocity < 40

    def test_a_ghost_note_and_a_snare_strike_the_same_drum(self):
        assert resolve("ghost_snare").note == resolve("snare").note

    def test_the_kick_is_the_gm_bass_drum(self):
        assert resolve("kick").note == 36


class TestKits:
    def test_every_kit_maps_to_a_preset(self):
        assert set(KIT_PRESETS) == set(Kit)

    def test_brushes_and_sticks_are_different_kits(self):
        assert KIT_PRESETS[Kit.BRUSH] != KIT_PRESETS[Kit.STANDARD]


class TestPromptMaterial:
    def test_the_kit_map_describes_every_piece(self):
        described = describe_kit()

        for name in piece_names():
            assert f'"{name}"' in described

    def test_every_piece_name_is_unique(self):
        assert len(piece_names()) == len(BY_NAME)

    def test_pieces_sit_in_the_gm_percussion_range(self):
        for piece in BY_NAME.values():
            assert 27 <= piece.note <= 87, piece.name
