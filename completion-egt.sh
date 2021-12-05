_egt() {
	COMPREPLY=()
	local cur="${COMP_WORDS[COMP_CWORD]}"
	local prev="${COMP_WORDS[COMP_CWORD-1]}"

	case "$prev" in
		edit|grep|term|work)
			local projects=$(egt completion projects)
			COMPREPLY=($(compgen -W "$projects" -- "$cur"))
		;;
		-t|--tag)
			local tags=$(egt completion tags)
			COMPREPLY=($(compgen -W "$tags" -- "$cur"))
		;;
	esac
	return 0
} 
complete -F _egt egt
